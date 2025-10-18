.PHONY: install serve-stt run-stt-sample run-stt-parliament test

install:
	python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt

serve-stt:
	uvicorn services.stt_server.main:app --host 0.0.0.0 --port 8089 --reload

run-stt-sample:
	python -m ingest.cli run stt --config-path examples/stt_sample_hls.json

run-stt-parliament:
	python -m ingest.cli run stt --config-path examples/stt_parliament.json

test:
	pytest -q
