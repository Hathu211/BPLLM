from typing import List, Optional, Union
import numpy as np
from sentence_transformers import SentenceTransformer

from bpllm.config import get_settings

class ProcessEmbedder:

# create 
  def __init__(self, model_name: Optional[str] = None):
    model_name = model_name or get_settings().embedding_model
    print(f" Loading embedding model: '{model_name}'...")
    self.model_name = model_name
    self.model = SentenceTransformer(model_name)
    self.vector_size = self.model.get_sentence_embedding_dimension()
    print(
        " Embedding model loaded successfully! Vector dimension:"
        f" {self.vector_size}."
    )

  def encode(
      self, texts: Union[str, List[str]], convert_to_list: bool = True
  ) -> Union[List[List[float]], List[float], np.ndarray]:
    """Encode a text string or a list of Process Chunks into vector embeddings."""
    is_single_string = isinstance(texts, str)
    if is_single_string:
      texts = [texts]

    if not texts:
      return []

    embeddings = self.model.encode(
        texts, show_progress_bar=False, normalize_embeddings=True
    )

    if convert_to_list:
      res = embeddings.tolist()
      return res[0] if is_single_string else res

    return embeddings[0] if is_single_string else embeddings