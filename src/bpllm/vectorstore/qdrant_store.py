"""Lưu và tìm chunk quy trình trong Qdrant (cosine, gRPC)."""
import uuid
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, PointStruct, VectorParams

from bpllm.config import get_settings

# Khóa payload dùng để lọc theo quy trình (food_delivery, ecommerce, reimbursement)
PROCESS_KEY = "process_id"
CHUNKING_KEY = "chunking"
CONTENT_KEY = "chunk_content"

ProcessFilter = Union[None, str, Iterable[str]]


def point_id(metadata: Dict[str, Any], fallback: int) -> str:
  """Id ổn định giữa các lần build: cùng process + node thì cùng id."""
  pid, nid = metadata.get(PROCESS_KEY), metadata.get("node_id")
  key = f"{pid}:{nid}" if pid and nid else f"chunk:{fallback}"
  return str(uuid.uuid5(uuid.NAMESPACE_URL, f"bpllm/{key}"))


def build_filter(process_filter: ProcessFilter) -> Optional[models.Filter]:
  """None = không lọc; 'food_delivery' = một quy trình; ['a', 'b'] = một trong các quy trình."""
  if process_filter is None:
    return None
  if isinstance(process_filter, str):
    values = [process_filter.strip()] if process_filter.strip() else []
  else:
    values = [p.strip() for p in process_filter if p and p.strip()]
  if not values:
    return None
  match = (models.MatchValue(value=values[0]) if len(values) == 1
           else models.MatchAny(any=values))
  return models.Filter(must=[models.FieldCondition(key=PROCESS_KEY, match=match)])


class QdrantVectorStore:
  """Quản lý một collection chứa chunk BPMN."""

  def __init__(self, collection_name: str, client: Optional[QdrantClient] = None):
    self.collection_name = collection_name
    if client is None:
      s = get_settings()
      print(f"Connecting to Qdrant at {s.qdrant_host} (HTTP {s.qdrant_http_port}, "
            f"gRPC {s.qdrant_grpc_port}), collection '{collection_name}'...")
      client = QdrantClient(host=s.qdrant_host, port=s.qdrant_http_port,
                            grpc_port=s.qdrant_grpc_port, prefer_grpc=s.qdrant_prefer_grpc)
    self.client = client

  def exists(self) -> bool:
    return self.client.collection_exists(self.collection_name)

  def count(self) -> int:
    return self.client.count(self.collection_name).count if self.exists() else 0

  def chunking(self) -> Optional[str]:
    """Kiểu chunk thật sự đang nằm trong collection (đọc từ payload của 1 điểm)."""
    if not self.exists():
      return None
    points, _ = self.client.scroll(self.collection_name, limit=1, with_payload=True)
    return points[0].payload.get(CHUNKING_KEY) if points else None

  def init_collection(self, vector_size: int, recreate: bool = True) -> None:
    """Tạo collection cosine; recreate=True thì xóa collection cũ trước."""
    if self.exists():
      if not recreate:
        return
      self.client.delete_collection(self.collection_name)
    self.client.create_collection(
        collection_name=self.collection_name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )
    self.client.create_payload_index(
        collection_name=self.collection_name, field_name=PROCESS_KEY,
        field_schema=models.PayloadSchemaType.KEYWORD,
    )

  def upsert_chunks(self, chunks: Sequence[str], embeddings: Sequence[Sequence[float]],
                    metadatas: Optional[Sequence[Dict[str, Any]]] = None) -> None:
    if len(chunks) != len(embeddings):
      raise ValueError("Số chunk và số vector phải bằng nhau")
    if metadatas is not None and len(metadatas) != len(chunks):
      raise ValueError("Số chunk và số metadata phải bằng nhau")
    points = []
    for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
      meta = dict(metadatas[i]) if metadatas else {}
      points.append(PointStruct(id=point_id(meta, i), vector=list(emb),
                                payload={CONTENT_KEY: chunk, **meta}))
    self.client.upsert(collection_name=self.collection_name, points=points, wait=True)

  def search_top_k(self, query_vector: Sequence[float], top_k: int = 10,
                   process_filter: ProcessFilter = None) -> List[Dict[str, Any]]:
    """Top-k chunk gần nhất theo cosine, có thể lọc theo một hoặc nhiều quy trình."""
    vector = list(query_vector)
    if vector and isinstance(vector[0], (list, tuple)):
      vector = list(vector[0])
    response = self.client.query_points(
        collection_name=self.collection_name, query=vector,
        query_filter=build_filter(process_filter), limit=top_k, with_payload=True,
    )
    return [{"score": hit.score,
             "content": hit.payload.get(CONTENT_KEY, ""),
             "metadata": {k: v for k, v in hit.payload.items() if k != CONTENT_KEY}}
            for hit in response.points]
