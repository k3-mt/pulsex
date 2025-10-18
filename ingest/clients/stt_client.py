from __future__ import annotations
import base64
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import requests

@dataclass
class Segment:
    start: float
    end: float
    text: str

@dataclass
class TranscribeRequest:
    stream_url: str
    language: str | None = None
    model_size: str = "base"
    chunk_seconds: int = 30
    max_seconds: int = 120
    device: str = "cpu"  # "cpu" or "cuda"

@dataclass
class TranscribeResponse:
    transcript: str
    segments: List[Segment]
    duration: float
    model: str
    sample_rate: int
    srt_text: str

class STTClient:
    """
    REST client for the local STT service.
    POST /transcribe_url -> {transcript, segments, duration, model, sample_rate, srt_b64}
    """
    def __init__(self, service_url: str, timeout: int = 180) -> None:
        self.service_url = service_url.rstrip("/")
        self.timeout = timeout

    def transcribe(self, req: TranscribeRequest) -> TranscribeResponse:
        url = f"{self.service_url}/transcribe_url"
        payload: Dict[str, Any] = {
            "stream_url": req.stream_url,
            "language": req.language,
            "model_size": req.model_size,
            "chunk_seconds": req.chunk_seconds,
            "max_seconds": req.max_seconds,
            "device": req.device,
        }
        r = requests.post(url, json=payload, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        srt_text = base64.b64decode(data["srt_b64"]).decode("utf-8")
        segments = [Segment(**seg) for seg in data["segments"]]
        return TranscribeResponse(
            transcript=data["transcript"],
            segments=segments,
            duration=data["duration"],
            model=data["model"],
            sample_rate=data["sample_rate"],
            srt_text=srt_text,
        )
