"""Nơi duy nhất đọc cấu hình. Giá trị lấy từ biến môi trường, rồi từ file .env ở gốc repo."""
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Thư mục gốc repo; đúng khi cài bằng `pip install -e .`
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
PROCESSED_DIR = DATA_DIR / "processed"
QUESTIONS_DIR = DATA_DIR / "questions"
RAG_INPUTS_DIR = DATA_DIR / "rag_inputs"
RESULTS_DIR = DATA_DIR / "results"

CHUNKINGS = ("specific", "enriched")
QUANTS = ("int4", "int8")

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


def _env_choice(name: str, default: str, choices) -> str:
  value = _env_str(name, default).lower()
  if value not in choices:
    raise ValueError(f"{name} phải là một trong {list(choices)}, nhận được '{value}'")
  return value


@dataclass(frozen=True)
class Settings:
  qdrant_host: str
  qdrant_http_port: int
  qdrant_grpc_port: int
  qdrant_prefer_grpc: bool
  collection_specific: str
  collection_enriched: str
  embedding_model: str
  top_k: int
  app_chunking: str
  llm_base_url: str
  llm_api_key: str
  llm_quant: str
  llm_max_tokens: int
  llm_timeout: int

  def collection(self, chunking: str) -> str:
    """Tên collection của một kiểu chunk ('specific' hoặc 'enriched')."""
    if chunking not in CHUNKINGS:
      raise ValueError(f"chunking phải là một trong {CHUNKINGS}, nhận được '{chunking}'")
    return self.collection_specific if chunking == "specific" else self.collection_enriched

  @classmethod
  def from_env(cls) -> "Settings":
    settings = cls(
        qdrant_host=_env_str("QDRANT_HOST", "localhost"),
        qdrant_http_port=_env_int("QDRANT_HTTP_PORT", 6343),
        qdrant_grpc_port=_env_int("QDRANT_GRPC_PORT", 6344),
        qdrant_prefer_grpc=_env_bool("QDRANT_PREFER_GRPC", True),
        collection_specific=_env_str("QDRANT_COLLECTION_SPECIFIC", "bpllm2_specific"),
        collection_enriched=_env_str("QDRANT_COLLECTION_ENRICHED", "bpllm2_enriched"),
        embedding_model=_env_str("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        top_k=_env_int("TOP_K", 10),
        app_chunking=_env_choice("APP_CHUNKING", "enriched", CHUNKINGS),
        llm_base_url=_env_str("LLM_BASE_URL", "http://localhost:8000/v1"),
        llm_api_key=_env_str("LLM_API_KEY", "change-me"),
        llm_quant=_env_choice("LLM_QUANT", "int4", QUANTS),
        llm_max_tokens=_env_int("LLM_MAX_TOKENS", 256),
        llm_timeout=_env_int("LLM_TIMEOUT", 300),
    )
    if settings.collection_specific == settings.collection_enriched:
      raise ValueError("QDRANT_COLLECTION_SPECIFIC và QDRANT_COLLECTION_ENRICHED phải khác nhau")
    return settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
  load_dotenv(PROJECT_ROOT / ".env")
  return Settings.from_env()
