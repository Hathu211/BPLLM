"""Dùng Qdrant in-memory nên không cần bật Docker."""
import pytest
from qdrant_client import QdrantClient

from bpllm.vectorstore import qdrant_store
from bpllm.vectorstore.qdrant_store import QdrantVectorStore, point_id


@pytest.fixture
def client_kwargs(monkeypatch):
  """Thay QdrantClient bằng bản in-memory và ghi lại tham số kết nối."""
  captured = {}

  def fake_client(**kwargs):
    captured.update(kwargs)
    return QdrantClient(":memory:")

  monkeypatch.setattr(qdrant_store, "QdrantClient", fake_client)
  return captured


def filled_store():
  store = QdrantVectorStore()
  store.init_collection(vector_size=2, recreate=True)
  store.upsert_chunks(
      ["food chunk", "shop chunk"],
      [[1.0, 0.0], [0.0, 1.0]],
      [{"process_id": "food_delivery", "node_id": "t1"},
       {"process_id": "ecommerce", "node_id": "t1"}],
  )
  return store


def test_connection_settings_come_from_config(client_kwargs, monkeypatch):
  monkeypatch.setenv("QDRANT_HOST", "qdrant.internal")
  monkeypatch.setenv("QDRANT_HTTP_PORT", "7333")
  monkeypatch.setenv("QDRANT_GRPC_PORT", "7334")
  monkeypatch.setenv("QDRANT_COLLECTION", "other")

  store = QdrantVectorStore()

  assert client_kwargs["host"] == "qdrant.internal"
  assert client_kwargs["port"] == 7333
  assert client_kwargs["grpc_port"] == 7334
  assert store.collection_name == "other"


def test_search_returns_closest_chunk_first(client_kwargs):
  results = filled_store().search_top_k([1.0, 0.0], top_k=2)
  assert [r["content"] for r in results] == ["food chunk", "shop chunk"]
  assert results[0]["metadata"] == {"process_id": "food_delivery", "node_id": "t1"}


def test_search_applies_process_filter(client_kwargs):
  results = filled_store().search_top_k([1.0, 0.0], top_k=2, process_filter="ecommerce")
  assert [r["content"] for r in results] == ["shop chunk"]


@pytest.mark.parametrize("no_filter", [None, "", "All Process Model"])
def test_all_processes_means_no_filter(client_kwargs, no_filter):
  results = filled_store().search_top_k([1.0, 0.0], top_k=2, process_filter=no_filter)
  assert len(results) == 2


def test_search_accepts_batched_query_vector(client_kwargs):
  results = filled_store().search_top_k([[1.0, 0.0]], top_k=1)
  assert results[0]["content"] == "food chunk"


def test_rebuild_replaces_points_instead_of_duplicating(client_kwargs):
  store = filled_store()
  store.upsert_chunks(["food chunk v2"], [[1.0, 0.0]],
                      [{"process_id": "food_delivery", "node_id": "t1"}])
  assert store.client.count(store.collection_name).count == 2


def test_point_id_is_stable_and_process_specific():
  a = point_id({"process_id": "food_delivery", "node_id": "t1"}, 0)
  assert a == point_id({"process_id": "food_delivery", "node_id": "t1"}, 5)
  assert a != point_id({"process_id": "ecommerce", "node_id": "t1"}, 0)


def test_init_collection_recreates_existing(client_kwargs):
  store = filled_store()
  store.init_collection(vector_size=2, recreate=True)
  assert store.client.count(store.collection_name).count == 0


def test_upsert_rejects_mismatched_lengths(client_kwargs):
  store = QdrantVectorStore()
  with pytest.raises(ValueError):
    store.upsert_chunks(["only one"], [[1.0, 0.0], [0.0, 1.0]])
