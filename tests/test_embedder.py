"""Dùng model giả để test chạy nhanh và không cần tải model từ mạng."""
import numpy as np
import pytest

from bpllm.embeddings import embedder as embedder_module
from bpllm.embeddings.embedder import ProcessEmbedder


class FakeModel:
  def __init__(self, name):
    self.name = name

  def get_sentence_embedding_dimension(self):
    return 3

  def encode(self, texts, **kwargs):
    return np.ones((len(texts), 3))


@pytest.fixture
def fake_model(monkeypatch):
  monkeypatch.setattr(embedder_module, "SentenceTransformer", FakeModel)


def test_model_name_comes_from_config(fake_model, monkeypatch):
  monkeypatch.setenv("EMBEDDING_MODEL", "some/model")
  assert ProcessEmbedder().model.name == "some/model"


def test_explicit_model_name_wins(fake_model, monkeypatch):
  monkeypatch.setenv("EMBEDDING_MODEL", "some/model")
  assert ProcessEmbedder("other/model").model_name == "other/model"


def test_single_string_returns_one_vector(fake_model):
  assert ProcessEmbedder().encode("hello") == [1.0, 1.0, 1.0]


def test_list_returns_one_vector_per_text(fake_model):
  vectors = ProcessEmbedder().encode(["a", "b"])
  assert len(vectors) == 2
  assert len(vectors[0]) == 3


def test_empty_list_returns_empty(fake_model):
  assert ProcessEmbedder().encode([]) == []
