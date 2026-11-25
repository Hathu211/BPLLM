"""Qdrant in-memory, không cần Docker."""
import pytest
from qdrant_client import QdrantClient

from bpllm.vectorstore.qdrant_store import QdrantVectorStore, build_filter, point_id


def filled_store():
  store = QdrantVectorStore("test", client=QdrantClient(":memory:"))
  store.init_collection(vector_size=2)
  store.upsert_chunks(
      ["food chunk", "shop chunk", "money chunk"],
      [[1.0, 0.0], [0.9, 0.1], [0.8, 0.2]],
      [{"process_id": "food_delivery", "node_id": "t1", "chunking": "enriched"},
       {"process_id": "ecommerce", "node_id": "t1", "chunking": "enriched"},
       {"process_id": "reimbursement", "node_id": "t1", "chunking": "enriched"}])
  return store


def contents(results):
  return [r["content"] for r in results]


def test_search_returns_closest_first_with_metadata():
  results = filled_store().search_top_k([1.0, 0.0], top_k=3)
  assert contents(results) == ["food chunk", "shop chunk", "money chunk"]
  assert results[0]["metadata"]["process_id"] == "food_delivery"


def test_filter_one_process():
  assert contents(filled_store().search_top_k([1.0, 0.0], 3, "ecommerce")) == ["shop chunk"]


def test_filter_several_processes_like_paper_table_4():
  results = filled_store().search_top_k([1.0, 0.0], 3, ["food_delivery", "reimbursement"])
  assert contents(results) == ["food chunk", "money chunk"]


@pytest.mark.parametrize("no_filter", [None, "", [], ["  "]])
def test_empty_filter_means_no_filter(no_filter):
  assert build_filter(no_filter) is None


def test_store_reports_its_chunking_and_count():
  store = filled_store()
  assert store.chunking() == "enriched"
  assert store.count() == 3


def test_missing_collection():
  store = QdrantVectorStore("missing", client=QdrantClient(":memory:"))
  assert not store.exists() and store.count() == 0 and store.chunking() is None


def test_batched_query_vector_is_accepted():
  assert filled_store().search_top_k([[1.0, 0.0]], top_k=1)[0]["content"] == "food chunk"


def test_rebuild_replaces_points():
  store = filled_store()
  store.upsert_chunks(["food v2"], [[1.0, 0.0]], [{"process_id": "food_delivery", "node_id": "t1"}])
  assert store.count() == 3


def test_init_collection_recreates():
  store = filled_store()
  store.init_collection(vector_size=2, recreate=True)
  assert store.count() == 0


def test_point_id_is_stable_and_process_specific():
  a = point_id({"process_id": "food_delivery", "node_id": "t1"}, 0)
  assert a == point_id({"process_id": "food_delivery", "node_id": "t1"}, 5)
  assert a != point_id({"process_id": "ecommerce", "node_id": "t1"}, 0)


def test_mismatched_lengths_are_rejected():
  with pytest.raises(ValueError):
    filled_store().upsert_chunks(["one"], [[1.0, 0.0], [0.0, 1.0]])
