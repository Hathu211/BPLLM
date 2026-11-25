import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Thư mục gốc repo; đúng khi cài bằng `pip install -e .`
PROJECT_ROOT = Path(__file__).resolve().parents[2]

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _env_str(name: str, default: str) -> str:
  value = os.environ.get(name, "").strip()
  return value or default


def _env_int(name: str, default: int) -> int:
  value = os.environ.get(name, "").strip()
  if not value:
    return default
  try:
    return int(value)
  except ValueError as exc:
    raise ValueError(f"{name} phải là số nguyên, nhận được '{value}'") from exc


def _env_bool(name: str, default: bool) -> bool:
  value = os.environ.get(name, "").strip().lower()
  if not value:
    return default
  if value in _TRUE_VALUES:
    return True
  if value in _FALSE_VALUES:
    return False
  raise ValueError(f"{name} phải là true hoặc false, nhận được '{value}'")


@dataclass(frozen=True)
class Settings:
  qdrant_host: str
  qdrant_http_port: int
  qdrant_grpc_port: int
  qdrant_prefer_grpc: bool
  qdrant_collection: str
  embedding_model: str

  @classmethod
  def from_env(cls) -> "Settings":
    return cls(
        qdrant_host=_env_str("QDRANT_HOST", "localhost"),
        qdrant_http_port=_env_int("QDRANT_HTTP_PORT", 6333),
        qdrant_grpc_port=_env_int("QDRANT_GRPC_PORT", 6334),
        qdrant_prefer_grpc=_env_bool("QDRANT_PREFER_GRPC", True),
        qdrant_collection=_env_str("QDRANT_COLLECTION", "bpllm_processes"),
        embedding_model=_env_str(
            "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        ),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
  load_dotenv(PROJECT_ROOT / ".env")
  return Settings.from_env()
