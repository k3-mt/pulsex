from __future__ import annotations
import re
from dataclasses import dataclass
from typing import List, Optional
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import SRTFormatter

@dataclass
class YouTubeSegment:
    start: float
    end: float
    text: str

@dataclass
class YouTubeTranscriptRequest:
    video_url: str
    languages: List[str] = None
    preserve_formatting: bool = False

@dataclass
class YouTubeTranscriptResponse:
    transcript: str
    segments: List[YouTubeSegment]
    video_id: str
    language: str
    language_code: str
    is_generated: bool
    srt_text: str

class YouTubeClient:
    """
    Client for YouTube Transcript API.
    Extracts video ID from YouTube URLs and fetches transcripts.
    """
    
    def __init__(self) -> None:
        self.api = YouTubeTranscriptApi()
        self.srt_formatter = SRTFormatter()
    
    def _extract_video_id(self, video_url: str) -> str:
        """Extract video ID from various YouTube URL formats."""
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([^&\n?#]+)',
            r'youtube\.com/v/([^&\n?#]+)',
            r'youtube\.com/watch\?.*v=([^&\n?#]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, video_url)
            if match:
                return match.group(1)
        
        raise ValueError(f"Could not extract video ID from URL: {video_url}")
    
    def get_transcript(self, req: YouTubeTranscriptRequest) -> YouTubeTranscriptResponse:
        """
        Fetch transcript for a YouTube video.
        
        Args:
            req: YouTube transcript request with video URL and options
            
        Returns:
            YouTube transcript response with segments and formatted text
        """
        video_id = self._extract_video_id(req.video_url)
        
        # Set default languages if not provided
        languages = req.languages or ['en']
        
        try:
            # Fetch the transcript
            fetched_transcript = self.api.fetch(
                video_id, 
                languages=languages,
                preserve_formatting=req.preserve_formatting
            )
            
            # Convert to our format
            segments = []
            transcript_parts = []
            
            for snippet in fetched_transcript:
                start = float(snippet.start)
                end = start + float(snippet.duration)
                text = snippet.text.strip()
                
                if text:
                    segments.append(YouTubeSegment(
                        start=start,
                        end=end,
                        text=text
                    ))
                    transcript_parts.append(text)
            
            # Generate SRT format - need to use the original snippet format
            srt_data = []
            for snippet in fetched_transcript:
                if snippet.text.strip():
                    srt_data.append(snippet)
            srt_text = self.srt_formatter.format_transcript(srt_data)
            
            return YouTubeTranscriptResponse(
                transcript=" ".join(transcript_parts).strip(),
                segments=segments,
                video_id=video_id,
                language=fetched_transcript.language,
                language_code=fetched_transcript.language_code,
                is_generated=fetched_transcript.is_generated,
                srt_text=srt_text
            )
            
        except Exception as e:
            raise Exception(f"Failed to fetch YouTube transcript: {str(e)}")
    
    def list_available_transcripts(self, video_url: str) -> dict:
        """
        List all available transcripts for a video.
        
        Args:
            video_url: YouTube video URL
            
        Returns:
            Dictionary with available transcript information
        """
        video_id = self._extract_video_id(video_url)
        
        try:
            transcript_list = self.api.list(video_id)
            
            available = {
                "video_id": video_id,
                "transcripts": []
            }
            
            for transcript in transcript_list:
                available["transcripts"].append({
                    "language": transcript.language,
                    "language_code": transcript.language_code,
                    "is_generated": transcript.is_generated,
                    "is_translatable": transcript.is_translatable
                })
            
            return available
            
        except Exception as e:
            raise Exception(f"Failed to list YouTube transcripts: {str(e)}")
