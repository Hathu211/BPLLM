import re

import pytest

from bpllm.config import PROJECT_ROOT, Settings

ENV_VARS = re.findall(r"^([A-Z_]+)=", (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8"),
                      re.MULTILINE)


@pytest.fixture
def clean_env(monkeypatch):
  for name in ENV_VARS:
    monkeypatch.delenv(name, raising=False)
  return monkeypatch


def test_env_example_lists_every_setting():
  assert len(ENV_VARS) == len(Settings.__dataclass_fields__)


def test_defaults(clean_env):
  s = Settings.from_env()
  assert (s.qdrant_host, s.qdrant_http_port, s.qdrant_grpc_port) == ("localhost", 6343, 6344)
  assert s.collection("specific") == "bpllm2_specific"
  assert s.collection("enriched") == "bpllm2_enriched"
  assert s.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
  assert s.top_k == 10
  assert s.app_chunking == "enriched"
  assert s.llm_quant == "int4"


def test_env_overrides_defaults(clean_env):
  clean_env.setenv("QDRANT_GRPC_PORT", "7344")
  clean_env.setenv("QDRANT_COLLECTION_ENRICHED", "other_enriched")
  clean_env.setenv("APP_CHUNKING", "specific")
  clean_env.setenv("LLM_QUANT", "int8")
  clean_env.setenv("LLM_BASE_URL", "https://x.trycloudflare.com/v1")
  s = Settings.from_env()
  assert s.qdrant_grpc_port == 7344
  assert s.collection("enriched") == "other_enriched"
  assert s.app_chunking == "specific"
  assert s.llm_quant == "int8"
  assert s.llm_base_url == "https://x.trycloudflare.com/v1"


def test_blank_value_uses_default(clean_env):
  clean_env.setenv("QDRANT_HOST", "   ")
  assert Settings.from_env().qdrant_host == "localhost"


@pytest.mark.parametrize("name, value", [("QDRANT_GRPC_PORT", "abc"), ("QDRANT_PREFER_GRPC", "maybe"),
                                         ("APP_CHUNKING", "fixed"), ("LLM_QUANT", "int2")])
def test_invalid_value_names_the_variable(clean_env, name, value):
  clean_env.setenv(name, value)
  with pytest.raises(ValueError, match=name):
    Settings.from_env()


def test_two_chunkings_cannot_share_a_collection(clean_env):
  clean_env.setenv("QDRANT_COLLECTION_SPECIFIC", "same")
  clean_env.setenv("QDRANT_COLLECTION_ENRICHED", "same")
  with pytest.raises(ValueError, match="khác nhau"):
    Settings.from_env()


def test_unknown_chunking_is_rejected(clean_env):
  with pytest.raises(ValueError):
    Settings.from_env().collection("fixed")
