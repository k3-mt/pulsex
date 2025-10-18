from __future__ import annotations
import json
from pathlib import Path
import typer
from pydantic import ValidationError
from ingest.core.base import PipelineRegistry
from ingest.pipelines.stt_pipeline import STTConfig, STTPipeline

app = typer.Typer(help="Ingestion framework CLI")

@app.command("list")
def list_pipelines():
    registry = PipelineRegistry.list()
    for name, cls in registry.items():
        typer.echo(f"{name}: {cls.__module__}.{cls.__name__}")

@app.command("run")
def run_pipeline(
    name: str = typer.Argument(..., help="Pipeline name, e.g., 'stt'"),
    config_path: Path = typer.Option(..., exists=True, dir_okay=False, help="Path to pipeline JSON config")
):
    registry = PipelineRegistry.list()
    if name not in registry:
        typer.echo(f"Pipeline '{name}' not found. Try 'python -m ingest.cli list'")
        raise typer.Exit(code=1)

    raw = json.loads(config_path.read_text())
    try:
        if name == "stt":
            cfg = STTConfig(**raw)
            pipeline = STTPipeline(cfg)
        else:
            typer.echo(f"Pipeline '{name}' is registered but not wired in CLI.")
            raise typer.Exit(code=1)
    except ValidationError as ve:
        typer.echo(f"Invalid config: {ve}")
        raise typer.Exit(code=1)

    result = pipeline.run()
    if result.success:
        typer.echo(json.dumps(result.data, indent=2))
    else:
        typer.echo(f"Pipeline failed: {result.error}")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
