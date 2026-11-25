"""Embedding bằng sentence-transformers (mặc định all-MiniLM-L6-v2, 384 chiều, như bài báo)."""
from typing import List, Optional, Union

import numpy as np
from sentence_transformers import SentenceTransformer

from bpllm.config import get_settings


class ProcessEmbedder:
  """Bọc SentenceTransformer; vector luôn được chuẩn hóa để dùng cosine / tích vô hướng."""

  def __init__(self, model_name: Optional[str] = None):
    self.model_name = model_name or get_settings().embedding_model
    print(f"Loading embedding model '{self.model_name}'...")
    self.model = SentenceTransformer(self.model_name)
    self.vector_size = self.model.get_sentence_embedding_dimension()
    print(f"Embedding model loaded, vector size {self.vector_size}.")

  def encode(self, texts: Union[str, List[str]], convert_to_list: bool = True
             ) -> Union[List[List[float]], List[float], np.ndarray]:
    """Một chuỗi -> một vector; danh sách -> danh sách vector."""
    single = isinstance(texts, str)
    if single:
      texts = [texts]
    if not texts:
      return []
    embeddings = self.model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    if convert_to_list:
      result = embeddings.tolist()
      return result[0] if single else result
    return embeddings[0] if single else embeddings
