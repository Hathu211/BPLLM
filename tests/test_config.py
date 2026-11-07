import pytest

from bpllm.config import Settings

ENV_VARS = [
    "QDRANT_HOST",
    "QDRANT_HTTP_PORT",
    "QDRANT_GRPC_PORT",
    "QDRANT_PREFER_GRPC",
    "QDRANT_COLLECTION",
    "EMBEDDING_MODEL",
]


@pytest.fixture
def clean_env(monkeypatch):
  for name in ENV_VARS:
    monkeypatch.delenv(name, raising=False)
  return monkeypatch


def test_defaults(clean_env):
  settings = Settings.from_env()
  assert settings.qdrant_host == "localhost"
  assert settings.qdrant_http_port == 6333
  assert settings.qdrant_grpc_port == 6334
  assert settings.qdrant_prefer_grpc is True
  assert settings.qdrant_collection == "bpllm_processes"
  assert settings.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"


def test_env_overrides_defaults(clean_env):
  clean_env.setenv("QDRANT_HOST", "qdrant.internal")
  clean_env.setenv("QDRANT_GRPC_PORT", "7334")
  clean_env.setenv("QDRANT_PREFER_GRPC", "false")
  clean_env.setenv("QDRANT_COLLECTION", "other")
  clean_env.setenv("EMBEDDING_MODEL", "some/model")

  settings = Settings.from_env()

  assert settings.qdrant_host == "qdrant.internal"
  assert settings.qdrant_grpc_port == 7334
  assert settings.qdrant_prefer_grpc is False
  assert settings.qdrant_collection == "other"
  assert settings.embedding_model == "some/model"


def test_blank_value_uses_default(clean_env):
  clean_env.setenv("QDRANT_HOST", "   ")
  clean_env.setenv("QDRANT_GRPC_PORT", "")
  settings = Settings.from_env()
  assert settings.qdrant_host == "localhost"
  assert settings.qdrant_grpc_port == 6334


def test_invalid_port_names_the_variable(clean_env):
  clean_env.setenv("QDRANT_GRPC_PORT", "abc")
  with pytest.raises(ValueError, match="QDRANT_GRPC_PORT"):
    Settings.from_env()


def test_invalid_bool_names_the_variable(clean_env):
  clean_env.setenv("QDRANT_PREFER_GRPC", "maybe")
  with pytest.raises(ValueError, match="QDRANT_PREFER_GRPC"):
    Settings.from_env()
