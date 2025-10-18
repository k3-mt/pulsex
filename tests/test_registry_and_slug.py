from ingest.pipelines.stt_pipeline import slugify
from ingest.core.base import PipelineRegistry

def test_slugify_basic():
    assert slugify("Hello, World!") == "hello-world"
    assert slugify("École — №1") == "ecole-no1"

def test_stt_registered():
    assert "stt" in PipelineRegistry.list()
