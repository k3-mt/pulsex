# Ingestion Framework

An extensible ingestion framework where each **pipeline** ingests/transforms content from a source.  
This build implements multiple ingestion pipelines:

- **STT Pipeline**: Speech-to-Text transcription from accessible audio/video URLs using faster-whisper
- **YouTube Pipeline**: Direct transcript extraction from YouTube videos using the [YouTube Transcript API](https://pypi.org/project/youtube-transcript-api/)

> ⚠️ **Legal & technical note**  
> Use this only with streams you are legally allowed to process. Many commercial players (e.g., BBC iPlayer) use DRM or require authentication. This service does **not** bypass DRM. If your target uses DRM, use the official, accessible feed (e.g., legislature-owned livestreams) or supply a non-DRM HLS `.m3u8` URL you control.

## Quickstart

### 0) Python & system deps
- Python **3.11+**
- **ffmpeg** installed and available on PATH (Linux/Mac: `brew install ffmpeg` or `apt-get install ffmpeg`) - *Required only for STT pipeline*

```bash
# Option 1: Use make (recommended)
make install

# Option 2: Manual setup
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt

# Option 3: Auto-activation (if you have direnv installed)
# brew install direnv
# direnv allow
# Then the virtual environment will auto-activate when you cd into this directory
```

## Available Pipelines

### YouTube Pipeline (No Service Required)

Extract transcripts directly from YouTube videos using the [YouTube Transcript API](https://pypi.org/project/youtube-transcript-api/).

```bash
# Activate virtual environment
source .venv/bin/activate  # or use: source activate.sh

# List available pipelines
python -m ingest.cli list

# Transcribe a YouTube video
python -m ingest.cli run youtube --config-path examples/youtube_sample.json

# Try with multiple language preferences
python -m ingest.cli run youtube --config-path examples/youtube_multilang.json
```

### STT Pipeline (Requires Service)

Transcribe audio/video streams using faster-whisper. Requires running a local service.

#### 1) Run the local STT service

This hosts a FastAPI server using faster-whisper. CPU works; GPU is optional.

⚠️ **IMPORTANT**: Always activate the virtual environment first!

```bash
# Activate virtual environment first (REQUIRED!)
source .venv/bin/activate  # or use: source activate.sh

# Start the service
uvicorn services.stt_server.main:app --host 0.0.0.0 --port 8089 --reload
```

Health check: http://localhost:8089/health

#### 2) Run the STT pipeline

In another terminal with the venv activated:

```bash
# Activate virtual environment
source .venv/bin/activate  # or use: source activate.sh

# Try an accessible HLS test stream (non-DRM)
python -m ingest.cli run stt --config-path examples/stt_sample_hls.json

# Or attempt a page you control / have rights to (may fail if DRM):
python -m ingest.cli run stt --config-path examples/stt_parliament.json
```

If successful, you'll see JSON output like:

**YouTube Pipeline:**
```json
{
  "video_url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "video_id": "VIDEO_ID",
  "language": "English",
  "language_code": "en",
  "is_generated": false,
  "requested_languages": ["en"],
  "preserve_formatting": false,
  "output_txt": "/abs/path/outputs/youtube/transcripts/sample_video.txt",
  "output_srt": "/abs/path/outputs/youtube/transcripts/sample_video.srt",
  "output_segments_json": "/abs/path/outputs/youtube/segments/sample_video.segments.json",
  "output_metadata_json": "/abs/path/outputs/youtube/segments/sample_video.metadata.json",
  "segment_count": 42,
  "total_duration": 180.5
}
```

**STT Pipeline:**
```json
{
  "stream_url": "...",
  "stt_service_url": "http://localhost:8089",
  "language": "en",
  "model_size": "base",
  "chunk_seconds": 30,
  "captured_seconds": 60.0,
  "output_txt": "/abs/path/outputs/stt/transcripts/mux_sample_demo.txt",
  "output_srt": "/abs/path/outputs/stt/transcripts/mux_sample_demo.srt",
  "output_segments_json": "/abs/path/outputs/stt/segments/mux_sample_demo.segments.json",
  "segment_count": 42,
  "sample_rate": 16000,
  "device": "cpu"
}
```

## Outputs

### YouTube Pipeline
- `outputs/youtube/transcripts/<name>.txt` – flat transcript
- `outputs/youtube/transcripts/<name>.srt` – captions with timestamps  
- `outputs/youtube/segments/<name>.segments.json` – list of {start,end,text}
- `outputs/youtube/segments/<name>.metadata.json` – video metadata and processing info

### STT Pipeline
- `outputs/stt/transcripts/<name>.txt` – flat transcript
- `outputs/stt/transcripts/<name>.srt` – captions with timestamps  
- `outputs/stt/segments/<name>.segments.json` – list of {start,end,text}

## Configuration

### YouTube Pipeline

`examples/youtube_sample.json` shows all options:

- `video_url` – YouTube video URL (supports various formats)
- `languages` – List of language codes in priority order (e.g., ["en", "es", "fr"])
- `preserve_formatting` – Keep HTML formatting (italics, bold, etc.)
- `output_dir` – Output directory
- `output_basename` – Custom filename prefix

### STT Pipeline

`examples/stt_sample_hls.json` shows all options:

- `stream_url` – HLS .m3u8 or other ffmpeg-readable URL (non-DRM)
- `language` – language hint (optional)
- `model_size` – tiny, base, small, medium, large-v3 (CPU: base/small recommended)
- `chunk_seconds` – split capture into fixed chunks; helps stability
- `max_seconds` – total capture duration before returning results
- `device` – cpu or cuda

## Notes & Tips

### YouTube Pipeline
- **No service required**: Works directly with YouTube's transcript API
- **Language support**: Automatically falls back to available languages if preferred language isn't available
- **Formatting**: Set `preserve_formatting: true` to keep HTML tags like `<i>` and `<b>`
- **Rate limits**: YouTube may rate limit requests; the API handles this gracefully

### STT Pipeline
- **DRM**: If your target uses DRM/auth, this pipeline will fail. Use official, non-DRM sources (e.g., legislature livestreams) or your own RTMP/HLS endpoints.
- **Speed/Cost**: tiny/base models are faster on CPU. small improves quality with modest slowdown.
- **GPU**: Run service with "device": "cuda" in your config for large models (ensure CUDA drivers).
- **Longer runs**: You can increase max_seconds and chunk_seconds; beware runtime increases accordingly.

## Testing

```bash
pytest -q
```

## Auto-activation

The project includes several ways to automatically activate the virtual environment:

1. **direnv** (recommended): Install with `brew install direnv`, then run `direnv allow` in the project directory
2. **Manual script**: Run `source activate.sh` 
3. **Make targets**: Use `make serve-stt`, `make run-stt-sample`, etc.

---