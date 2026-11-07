from typing import Any, Dict, List, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, PointStruct, VectorParams

from bpllm.config import get_settings


class QdrantVectorStore:
  """Manager class for interacting with Qdrant Vector DB."""

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
    print(f"Connecting to Qdrant DB at {host} (gRPC Port: {grpc_port})...")

    self.client = QdrantClient(
        host=host,
        port=settings.qdrant_http_port,
        grpc_port=grpc_port,
        prefer_grpc=prefer_grpc,
    )
    print("Qdrant gRPC connection established successfully!")

  def init_collection(
      self, vector_size: int = 384, recreate: bool = True
  ) -> None:
    """Initialize or recreate a collection with Cosine Distance metric."""
    collections = [c.name for c in self.client.get_collections().collections]

    if self.collection_name in collections and not recreate:
      print(f"Collection '{self.collection_name}' already exists.")
      return

    self.client.recreate_collection(
        collection_name=self.collection_name,
        vectors_config=VectorParams(
            size=vector_size, distance=Distance.COSINE
        ),
    )
    print(
        f" Successfully initialized collection '{self.collection_name}'"
        f" (Vector Size: {vector_size}, Metric: Cosine)!"
    )

  def upsert_chunks(
      self,
      chunks: List[str],
      embeddings: List[List[float]],
      metadatas: Optional[List[Dict[str, Any]]] = None,
  ) -> None:
    """Upsert Process Chunks and their embeddings into Qdrant Index."""
    if len(chunks) != len(embeddings):
      raise ValueError("Number of chunks and embeddings must be equal!")

    points = []
    for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
      payload = {"chunk_content": chunk}
      if metadatas and idx < len(metadatas):
        payload.update(metadatas[idx])

      points.append(PointStruct(id=idx + 1, vector=emb, payload=payload))

    self.client.upsert(collection_name=self.collection_name, points=points)
    print(
        f"Successfully stored {len(points)} points/vectors into Qdrant"
        " Index!"
    )

  def search_top_k(
      self,
      query_vector: List[float],
      top_k: int = 10,
      process_filter: Optional[str] = None,
  ) -> List[Dict[str, Any]]:
    """Retrieve top-K most similar chunks using Cosine Similarity with robust process filtering."""
    # Safety Check: Unwrap 2D list [[...]] to 1D list [...]
    if (
        isinstance(query_vector, list)
        and len(query_vector) > 0
        and isinstance(query_vector, list)
    ):
      query_vector = query_vector

    query_filter = None
    if process_filter and process_filter not in [
        "Tất cả quy trình",
        "All Processes",
        "",
        None,
    ]:
      # Tạo danh sách tất cả các dạng viết của tên quy trình
      clean_filter = process_filter.strip()
      possible_matches = [
          clean_filter,  # "Food Delivery"
          clean_filter.lower(),  # "food delivery"
          clean_filter.lower().replace(" ", "_"),  # "food_delivery"
          clean_filter.lower().replace("-", "_"),  # "food_delivery"
          clean_filter.replace("_", " ").title(),  # "Food Delivery"
          f"{clean_filter.lower().replace(' ', '_')}_gt",  # "food_delivery_gt"
      ]

      query_filter = models.Filter(
          must=[
              models.FieldCondition(
                  key="process",
                  match=models.MatchAny(
                      any=list(set(possible_matches))
                  ),  # Match bất kỳ dạng nào
              )
          ]
      )
    if hasattr(self.client, "query_point"): 
        respone = self.client.query.points(
            collection_name = self.collection_name,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=top_k,
        )
        hits = response.points
    elif hasattr(self.client, "query_point"): 
        response = self.client.query_point(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=top_k,
        )
        hits = getattr(response, "points", response)
    else:
      # API cũ (< 1.10.0)
        hits = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            query_filter=query_filter,
            limit=top_k,
        )
    results = []
    for hit in hits:
      results.append({
          "score": hit.score,
          "content": hit.payload.get("chunk_content", ""),
          "metadata": {
              k: v for k, v in hit.payload.items() if k != "chunk_content"
          },
      })
    return results