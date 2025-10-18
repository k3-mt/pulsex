from __future__ import annotations
import json
import re
import unicodedata
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator
from ingest.core.base import Pipeline, PipelineResult, PipelineRegistry
from ingest.clients.youtube_client import YouTubeClient, YouTubeTranscriptRequest

def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9\-_.]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-").lower()
    return value or "youtube-video"

class YouTubeConfig(BaseModel):
    video_url: HttpUrl = Field(..., description="YouTube video URL (e.g., https://www.youtube.com/watch?v=VIDEO_ID)")
    languages: List[str] = Field(["en"], description="List of language codes in priority order (e.g., ['en', 'es', 'fr'])")
    preserve_formatting: bool = Field(False, description="Preserve HTML formatting in transcripts (italics, bold, etc.)")
    output_dir: str = Field("outputs/youtube", description="Directory for transcripts and segment JSON.")
    output_basename: Optional[str] = Field(None, description="Optional base filename without extension.")

    @field_validator("output_dir")
    @classmethod
    def ensure_dir(cls, v: str) -> str:
        Path(v).mkdir(parents=True, exist_ok=True)
        (Path(v) / "transcripts").mkdir(parents=True, exist_ok=True)
        (Path(v) / "segments").mkdir(parents=True, exist_ok=True)
        return v

    @field_validator("video_url")
    @classmethod
    def validate_youtube_url(cls, v: str) -> str:
        """Validate that the URL is a YouTube URL."""
        youtube_patterns = [
            r'youtube\.com/watch\?v=',
            r'youtu\.be/',
            r'youtube\.com/embed/',
            r'youtube\.com/v/'
        ]
        
        if not any(re.search(pattern, str(v)) for pattern in youtube_patterns):
            raise ValueError("URL must be a valid YouTube video URL")
        
        return v

class YouTubePipeline(Pipeline):
    def __init__(self, config: YouTubeConfig) -> None:
        self.config = config

    def run(self) -> PipelineResult:
        try:
            client = YouTubeClient()
            req = YouTubeTranscriptRequest(
                video_url=str(self.config.video_url),
                languages=self.config.languages,
                preserve_formatting=self.config.preserve_formatting
            )
            resp = client.get_transcript(req)

            # Generate output filename
            base = self.config.output_basename or f"youtube_{resp.video_id}"
            out_dir = Path(self.config.output_dir)
            txt_path = out_dir / "transcripts" / f"{base}.txt"
            srt_path = out_dir / "transcripts" / f"{base}.srt"
            seg_path = out_dir / "segments" / f"{base}.segments.json"
            meta_path = out_dir / "segments" / f"{base}.metadata.json"

            # Write transcript files
            txt_path.write_text(resp.transcript, encoding="utf-8")
            srt_path.write_text(resp.srt_text, encoding="utf-8")
            
            # Write segments JSON
            seg_data = [
                {"start": s.start, "end": s.end, "text": s.text}
                for s in resp.segments
            ]
            seg_path.write_text(json.dumps(seg_data, indent=2), encoding="utf-8")
            
            # Write metadata JSON
            metadata = {
                "video_id": resp.video_id,
                "video_url": str(self.config.video_url),
                "language": resp.language,
                "language_code": resp.language_code,
                "is_generated": resp.is_generated,
                "requested_languages": self.config.languages,
                "preserve_formatting": self.config.preserve_formatting,
                "segment_count": len(resp.segments),
                "total_duration": resp.segments[-1].end if resp.segments else 0.0
            }
            meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

            return PipelineResult(
                success=True,
                data={
                    "video_url": str(self.config.video_url),
                    "video_id": resp.video_id,
                    "language": resp.language,
                    "language_code": resp.language_code,
                    "is_generated": resp.is_generated,
                    "requested_languages": self.config.languages,
                    "preserve_formatting": self.config.preserve_formatting,
                    "output_txt": str(txt_path.resolve()),
                    "output_srt": str(srt_path.resolve()),
                    "output_segments_json": str(seg_path.resolve()),
                    "output_metadata_json": str(meta_path.resolve()),
                    "segment_count": len(resp.segments),
                    "total_duration": resp.segments[-1].end if resp.segments else 0.0,
                },
                error=None,
            )
        except Exception as e:
            return PipelineResult(success=False, data={}, error=str(e))

# Register
PipelineRegistry.register("youtube", YouTubePipeline)
