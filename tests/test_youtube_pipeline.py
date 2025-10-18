import pytest
from unittest.mock import Mock, patch
from ingest.pipelines.youtube_pipeline import YouTubeConfig, YouTubePipeline, slugify
from ingest.clients.youtube_client import YouTubeClient, YouTubeTranscriptRequest
from ingest.core.base import PipelineRegistry


def test_slugify_basic():
    assert slugify("Hello, World!") == "hello-world"
    assert slugify("École — №1") == "ecole-no1"
    assert slugify("YouTube Video Title") == "youtube-video-title"


def test_youtube_config_validation():
    # Valid YouTube URL
    config = YouTubeConfig(
        video_url="https://www.youtube.com/watch?v=FTU1ExId7O4",
        languages=["en"],
        preserve_formatting=False
    )
    assert str(config.video_url) == "https://www.youtube.com/watch?v=FTU1ExId7O4"
    assert config.languages == ["en"]
    assert config.preserve_formatting is False

    # Test URL validation
    with pytest.raises(ValueError, match="URL must be a valid YouTube video URL"):
        YouTubeConfig(video_url="https://example.com/video")


def test_youtube_pipeline_registered():
    assert "youtube" in PipelineRegistry.list()


@patch('ingest.pipelines.youtube_pipeline.YouTubeClient')
def test_youtube_pipeline_success(mock_client_class):
    # Mock the client and its response
    mock_client = Mock()
    mock_client_class.return_value = mock_client
    
    # Mock transcript response
    mock_response = Mock()
    mock_response.transcript = "Hello world this is a test"
    mock_response.video_id = "FTU1ExId7O4"
    mock_response.language = "English"
    mock_response.language_code = "en"
    mock_response.is_generated = False
    mock_response.srt_text = "1\n00:00:00,000 --> 00:00:02,000\nHello world this is a test\n"
    mock_response.segments = [
        Mock(start=0.0, end=2.0, text="Hello world this is a test")
    ]
    
    mock_client.get_transcript.return_value = mock_response
    
    # Create pipeline and run
    config = YouTubeConfig(
        video_url="https://www.youtube.com/watch?v=FTU1ExId7O4",
        languages=["en"],
        output_basename="test_video"
    )
    
    pipeline = YouTubePipeline(config)
    result = pipeline.run()
    
    # Verify success
    assert result.success is True
    assert result.error is None
    assert result.data["video_id"] == "FTU1ExId7O4"
    assert result.data["language"] == "English"
    assert result.data["segment_count"] == 1
    assert "output_txt" in result.data
    assert "output_srt" in result.data
    assert "output_segments_json" in result.data
    assert "output_metadata_json" in result.data


@patch('ingest.pipelines.youtube_pipeline.YouTubeClient')
def test_youtube_pipeline_failure(mock_client_class):
    # Mock the client to raise an exception
    mock_client = Mock()
    mock_client_class.return_value = mock_client
    mock_client.get_transcript.side_effect = Exception("Video not found")
    
    # Create pipeline and run
    config = YouTubeConfig(
        video_url="https://www.youtube.com/watch?v=invalid",
        languages=["en"]
    )
    
    pipeline = YouTubePipeline(config)
    result = pipeline.run()
    
    # Verify failure
    assert result.success is False
    assert result.error == "Video not found"
    assert result.data == {}


def test_youtube_client_video_id_extraction():
    client = YouTubeClient()
    
    # Test various YouTube URL formats
    test_cases = [
        ("https://www.youtube.com/watch?v=FTU1ExId7O4", "FTU1ExId7O4"),
        ("https://youtu.be/FTU1ExId7O4", "FTU1ExId7O4"),
        ("https://www.youtube.com/embed/FTU1ExId7O4", "FTU1ExId7O4"),
        ("https://www.youtube.com/watch?v=FTU1ExId7O4&t=30s", "FTU1ExId7O4"),
    ]
    
    for url, expected_id in test_cases:
        assert client._extract_video_id(url) == expected_id
    
    # Test invalid URL
    with pytest.raises(ValueError, match="Could not extract video ID"):
        client._extract_video_id("https://example.com/video")


@patch('ingest.clients.youtube_client.YouTubeTranscriptApi')
def test_youtube_client_get_transcript(mock_api_class):
    # Mock the API
    mock_api = Mock()
    mock_api_class.return_value = mock_api
    
    # Mock the fetched transcript
    mock_fetched = Mock()
    mock_fetched.language = "English"
    mock_fetched.language_code = "en"
    mock_fetched.is_generated = False
    
    # Mock segments
    mock_segment1 = Mock()
    mock_segment1.start = 0.0
    mock_segment1.duration = 2.0
    mock_segment1.text = "Hello world"
    
    mock_segment2 = Mock()
    mock_segment2.start = 2.0
    mock_segment2.duration = 3.0
    mock_segment2.text = "this is a test"
    
    mock_fetched.__iter__ = Mock(return_value=iter([mock_segment1, mock_segment2]))
    
    mock_api.fetch.return_value = mock_fetched
    
    # Test the client
    client = YouTubeClient()
    request = YouTubeTranscriptRequest(
        video_url="https://www.youtube.com/watch?v=FTU1ExId7O4",
        languages=["en"]
    )
    
    response = client.get_transcript(request)
    
    # Verify response
    assert response.video_id == "FTU1ExId7O4"
    assert response.language == "English"
    assert response.language_code == "en"
    assert response.is_generated is False
    assert len(response.segments) == 2
    assert response.segments[0].text == "Hello world"
    assert response.segments[1].text == "this is a test"
    assert "Hello world this is a test" in response.transcript
