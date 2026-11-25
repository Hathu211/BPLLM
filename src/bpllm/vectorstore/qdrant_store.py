"""Lưu và tìm chunk quy trình trong Qdrant (cosine, gRPC)."""
import uuid
from typing import Any, Dict, List, Optional, Sequence

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, PointStruct, VectorParams

from bpllm.config import get_settings

# Khóa payload dùng để lọc theo quy trình (giá trị: food_delivery, ecommerce, reimbursement)
PROCESS_KEY = "process_id"
CONTENT_KEY = "chunk_content"
DEFAULT_TOP_K = 10

# Giá trị nghĩa là "không lọc" (giữ để tương thích với Streamlit cũ)
_NO_FILTER = {"", "all", "all process model", "all processes", "tất cả quy trình"}


def point_id(metadata: Dict[str, Any], fallback: int) -> str:
  """Id ổn định giữa các lần build: cùng process + node thì cùng id."""
  pid, nid = metadata.get(PROCESS_KEY), metadata.get("node_id")
  key = f"{pid}:{nid}" if pid and nid else f"chunk:{fallback}"
  return str(uuid.uuid5(uuid.NAMESPACE_URL, f"bpllm/{key}"))


class QdrantVectorStore:
  """Quản lý collection chứa chunk BPMN trong Qdrant."""

  def __init__(
      self,
      host: Optional[str] = None,
      grpc_port: Optional[int] = None,
      prefer_grpc: Optional[bool] = None,
      collection_name: Optional[str] = None,
  ):
    settings = get_settings()
    host = settings.qdrant_host if host is None else host
    grpc_port = settings.qdrant_grpc_port if grpc_port is None else grpc_port
    if prefer_grpc is None:
      prefer_grpc = settings.qdrant_prefer_grpc
    self.collection_name = collection_name or settings.qdrant_collection
    print(f"Connecting to Qdrant at {host} (gRPC port {grpc_port})...")

    self.client = QdrantClient(
        host=host,
        port=settings.qdrant_http_port,
        grpc_port=grpc_port,
        prefer_grpc=prefer_grpc,
    )

  def init_collection(self, vector_size: int = 384, recreate: bool = True) -> None:
    """Tạo collection cosine; recreate=True thì xóa collection cũ trước."""
    exists = self.client.collection_exists(self.collection_name)
    if exists and not recreate:
      print(f"Collection '{self.collection_name}' already exists.")
      return
    if exists:
      self.client.delete_collection(self.collection_name)

    self.client.create_collection(
        collection_name=self.collection_name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )
    # Index cho trường lọc để filter theo quy trình nhanh và chính xác
    self.client.create_payload_index(
        collection_name=self.collection_name,
        field_name=PROCESS_KEY,
        field_schema=models.PayloadSchemaType.KEYWORD,
    )
    print(f"Created collection '{self.collection_name}' (size {vector_size}, cosine).")

  def upsert_chunks(
      self,
      chunks: Sequence[str],
      embeddings: Sequence[Sequence[float]],
      metadatas: Optional[Sequence[Dict[str, Any]]] = None,
  ) -> None:
    """Lưu chunk + vector + metadata vào collection."""
    if len(chunks) != len(embeddings):
      raise ValueError("Number of chunks and embeddings must be equal!")
    if metadatas is not None and len(metadatas) != len(chunks):
      raise ValueError("Number of chunks and metadatas must be equal!")

    points = []
    for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
      meta = dict(metadatas[idx]) if metadatas else {}
      payload = {CONTENT_KEY: chunk, **meta}
      points.append(PointStruct(id=point_id(meta, idx), vector=list(emb), payload=payload))

    self.client.upsert(collection_name=self.collection_name, points=points, wait=True)
    print(f"Stored {len(points)} points in '{self.collection_name}'.")

  @staticmethod
  def build_filter(process_filter: Optional[str]) -> Optional[models.Filter]:
    """process_filter là process_id (vd 'food_delivery'); None/'All...' = không lọc."""
    if process_filter is None or process_filter.strip().lower() in _NO_FILTER:
      return None
    return models.Filter(must=[
        models.FieldCondition(key=PROCESS_KEY,
                              match=models.MatchValue(value=process_filter.strip()))
    ])

  def search_top_k(
      self,
      query_vector: Sequence[float],
      top_k: int = DEFAULT_TOP_K,
      process_filter: Optional[str] = None,
  ) -> List[Dict[str, Any]]:
    """Top-k chunk gần nhất theo cosine, có thể lọc theo một quy trình."""
    vector = list(query_vector)
    if vector and isinstance(vector[0], (list, tuple)):
      vector = list(vector[0])  # chấp nhận [[...]] từ encode() trả về batch

    response = self.client.query_points(
        collection_name=self.collection_name,
        query=vector,
        query_filter=self.build_filter(process_filter),
        limit=top_k,
        with_payload=True,
    )
    return [
        {
            "score": hit.score,
            "content": hit.payload.get(CONTENT_KEY, ""),
            "metadata": {k: v for k, v in hit.payload.items() if k != CONTENT_KEY},
        }
        for hit in response.points
    ]
