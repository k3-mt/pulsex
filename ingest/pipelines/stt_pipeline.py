from __future__ import annotations
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator
from ingest.core.base import Pipeline, PipelineResult, PipelineRegistry
from ingest.clients.stt_client import STTClient, TranscribeRequest

def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9\-_.]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-").lower()
    return value or "audio"

class STTConfig(BaseModel):
    stream_url: HttpUrl = Field(..., description="Audio/Video URL (e.g., HLS .m3u8) you are legally permitted to process.")
    stt_service_url: HttpUrl = Field(..., description="Base URL of STT service, e.g., http://localhost:8089")
    language: Optional[str] = Field(None, description="ISO language hint for Whisper (e.g., 'en'). If null, auto-detect.")
    model_size: str = Field("base", description="Whisper model size: tiny, base, small, medium, large-v3 (CPU: tiny/base/small recommended).")
    chunk_seconds: int = Field(30, ge=10, le=120, description="Cut the stream into N-second WAV chunks for batch transcription.")
    max_seconds: int = Field(120, ge=20, le=600, description="Total capture duration before returning a result.")
    device: str = Field("cpu", description="Device for faster-whisper: 'cpu' or 'cuda'.")
    output_dir: str = Field("outputs/stt", description="Directory for transcripts and segment JSON.")
    output_basename: Optional[str] = Field(None, description="Optional base filename without extension.")

    @field_validator("output_dir")
    @classmethod
    def ensure_dir(cls, v: str) -> str:
        Path(v).mkdir(parents=True, exist_ok=True)
        (Path(v) / "transcripts").mkdir(parents=True, exist_ok=True)
        (Path(v) / "segments").mkdir(parents=True, exist_ok=True)
        return v

class STTPipeline(Pipeline):
    def __init__(self, config: STTConfig) -> None:
        self.config = config

    def run(self) -> PipelineResult:
        try:
            client = STTClient(service_url=str(self.config.stt_service_url))
            req = TranscribeRequest(
                stream_url=str(self.config.stream_url),
                language=self.config.language,
                model_size=self.config.model_size,
                chunk_seconds=self.config.chunk_seconds,
                max_seconds=self.config.max_seconds,
                device=self.config.device,
            )
            resp = client.transcribe(req)

            base = self.config.output_basename or slugify(str(self.config.stream_url))
            out_dir = Path(self.config.output_dir)
            txt_path = out_dir / "transcripts" / f"{base}.txt"
            srt_path = out_dir / "transcripts" / f"{base}.srt"
            seg_path = out_dir / "segments" / f"{base}.segments.json"

            txt_path.write_text(resp.transcript, encoding="utf-8")
            srt_path.write_text(resp.srt_text, encoding="utf-8")
            seg_data = [
                {"start": s.start, "end": s.end, "text": s.text}
                for s in resp.segments
            ]
            seg_path.write_text(json.dumps(seg_data, indent=2), encoding="utf-8")

            return PipelineResult(
                success=True,
                data={
                    "stream_url": str(self.config.stream_url),
                    "stt_service_url": str(self.config.stt_service_url),
                    "language": self.config.language,
                    "model_size": self.config.model_size,
                    "chunk_seconds": self.config.chunk_seconds,
                    "captured_seconds": resp.duration,
                    "output_txt": str(txt_path.resolve()),
                    "output_srt": str(srt_path.resolve()),
                    "output_segments_json": str(seg_path.resolve()),
                    "segment_count": len(resp.segments),
                    "sample_rate": resp.sample_rate,
                    "device": self.config.device,
                },
                error=None,
            )
        except Exception as e:
            return PipelineResult(success=False, data={}, error=str(e))

# Register
PipelineRegistry.register("stt", STTPipeline)
