from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Type

@dataclass(frozen=True)
class PipelineResult:
    success: bool
    data: Dict[str, Any]
    error: str | None = None

class Pipeline(ABC):
    """Abstract pipeline interface."""
    @abstractmethod
    def run(self) -> PipelineResult:
        raise NotImplementedError

class PipelineRegistry:
    _registry: Dict[str, Type[Pipeline]] = {}

    @classmethod
    def register(cls, name: str, pipeline_cls: Type[Pipeline]) -> None:
        if name in cls._registry:
            raise ValueError(f"Pipeline '{name}' already registered.")
        cls._registry[name] = pipeline_cls

    @classmethod
    def get(cls, name: str) -> Type[Pipeline]:
        if name not in cls._registry:
            raise KeyError(f"Pipeline '{name}' not found. Registered: {list(cls._registry)}")
        return cls._registry[name]

    @classmethod
    def list(cls) -> Dict[str, Type[Pipeline]]:
        return dict(cls._registry)
