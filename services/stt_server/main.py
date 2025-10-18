from __future__ import annotations
import base64
import os
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from faster_whisper import WhisperModel

app = FastAPI(title="Local STT Service (Whisper via faster-whisper)")

# Cache models by size to avoid reloading on each request
_MODEL_CACHE: Dict[Tuple[str, str], WhisperModel] = {}  # key: (model_size, device)

def get_model(model_size: str, device: str) -> WhisperModel:
    key = (model_size, device)
    if key not in _MODEL_CACHE:
        # compute_type: lower precision is faster on CPU; keep int8 for CPU
        compute_type = "int8" if device == "cpu" else "float16"
        _MODEL_CACHE[key] = WhisperModel(model_size, device=device, compute_type=compute_type)
    return _MODEL_CACHE[key]

def ensure_ffmpeg() -> None:
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        raise HTTPException(status_code=500, detail="ffmpeg not found in PATH. Please install ffmpeg.")

def wav_duration_sec(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        frames = w.getnframes()
        rate = w.getframerate()
        return frames / float(rate)

def run_ffmpeg_segment(stream_url: str, out_dir: Path, chunk_seconds: int, max_seconds: int) -> List[Path]:
    """
    Uses ffmpeg to capture up to max_seconds from stream_url, splitting into chunk_seconds WAV files.
    """
    out_pattern = str(out_dir / "chunk_%04d.wav")
    cmd = [
        "ffmpeg",
        "-y",
        "-i", stream_url,
        "-t", str(max_seconds),
        "-vn",
        "-ac", "1",
        "-ar", "16000",
        "-f", "segment",
        "-segment_time", str(chunk_seconds),
        "-reset_timestamps", "1",
        "-c:a", "pcm_s16le",
        out_pattern,
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise HTTPException(
            status_code=400,
            detail=f"ffmpeg failed to read the stream. stderr: {proc.stderr.decode(errors='ignore')[:1000]}"
        )
    files = sorted(out_dir.glob("chunk_*.wav"))
    if not files:
        raise HTTPException(status_code=400, detail="No audio chunks produced; the URL may be inaccessible or protected.")
    return files

def to_srt(segments: List[Dict[str, float | str]]) -> str:
    def fmt_time(s: float) -> str:
        ms = int(round(s * 1000))
        h = ms // 3_600_000
        ms -= h * 3_600_000
        m = ms // 60_000
        ms -= m * 60_000
        sec = ms // 1000
        ms -= sec * 1000
        return f"{h:02}:{m:02}:{sec:02},{ms:03}"

    lines = []
    for idx, seg in enumerate(segments, start=1):
        start = float(seg["start"])
        end = float(seg["end"])
        text = str(seg["text"]).strip()
        lines.append(f"{idx}")
        lines.append(f"{fmt_time(start)} --> {fmt_time(end)}")
        lines.append(text)
        lines.append("")  # blank line
    return "\n".join(lines).strip() + "\n"

class TranscribeUrlRequest(BaseModel):
    stream_url: str = Field(..., description="Audio/Video URL (e.g., HLS .m3u8) you are permitted to process.")
    language: Optional[str] = Field(None, description="Language hint, e.g., 'en'. If null, auto-detect.")
    model_size: str = Field("base", description="Whisper model size (tiny, base, small, medium, large-v3).")
    chunk_seconds: int = Field(30, ge=10, le=120)
    max_seconds: int = Field(120, ge=20, le=600)
    device: str = Field("cpu", description="'cpu' or 'cuda'")

class SegmentOut(BaseModel):
    start: float
    end: float
    text: str

class TranscribeUrlResponse(BaseModel):
    transcript: str
    segments: List[SegmentOut]
    duration: float
    model: str
    sample_rate: int
    srt_b64: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/transcribe_url", response_model=TranscribeUrlResponse)
def transcribe_url(req: TranscribeUrlRequest):
    """
    Capture N seconds from a URL, split into chunks, transcribe with Whisper, and return:
    - full transcript
    - timecoded segments
    - SRT (base64) for convenience
    """
    ensure_ffmpeg()
    model = get_model(req.model_size, req.device)

    tmp_root = Path(tempfile.mkdtemp(prefix="stt_service_"))
    chunks_dir = tmp_root / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)

    try:
        chunk_files = run_ffmpeg_segment(
            stream_url=req.stream_url,
            out_dir=chunks_dir,
            chunk_seconds=req.chunk_seconds,
            max_seconds=req.max_seconds,
        )

        segments_out: List[Dict[str, float | str]] = []
        transcript_parts: List[str] = []
        offset = 0.0

        # Transcribe each chunk in order
        for i, wav_path in enumerate(chunk_files):
            # Use measured duration for accurate offsets
            if i > 0:
                offset += wav_duration_sec(chunk_files[i - 1])

            # Transcribe
            gen = model.transcribe(
                str(wav_path),
                language=req.language,
                vad_filter=True,
                beam_size=5 if req.device == "cpu" else 1,  # modest quality on CPU
            )

            for seg in gen[0]:  # segments iterator
                start = float(seg.start) + offset
                end = float(seg.end) + offset
                text = seg.text.strip()
                if text:
                    segments_out.append({"start": start, "end": end, "text": text})
                    transcript_parts.append(text)

        transcript = " ".join(transcript_parts).strip()
        total_duration = sum(wav_duration_sec(p) for p in chunk_files)
        srt_text = to_srt(segments_out)
        srt_b64 = base64.b64encode(srt_text.encode("utf-8")).decode("ascii")

        return TranscribeUrlResponse(
            transcript=transcript,
            segments=[SegmentOut(**s) for s in segments_out],
            duration=total_duration,
            model=f"faster-whisper:{req.model_size}",
            sample_rate=16000,
            srt_b64=srt_b64,
        )
    finally:
        # Cleanup temp directory
        try:
            shutil.rmtree(tmp_root, ignore_errors=True)
        except Exception:
            pass
