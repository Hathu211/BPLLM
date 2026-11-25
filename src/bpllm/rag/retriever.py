"""Embed câu hỏi rồi lấy top-k chunk trong Qdrant."""
import re
from typing import Any, Dict, List

from bpllm.vectorstore.qdrant_store import ProcessFilter

_BOILERPLATE = [
    re.compile(r"^\s*Ignore your previous answers\.\s*", re.IGNORECASE),
    re.compile(r"\s*Also reference the corresponding piece of provided context if present\.?\s*$",
               re.IGNORECASE),
]


def clean_query(question: str) -> str:
  """Bỏ phần câu lệnh lặp lại, chỉ giữ nội dung hỏi để embed (không đổi câu gửi LLM)."""
  for pattern in _BOILERPLATE:
    question = pattern.sub("", question)
  return question.strip()


class Retriever:
  """clean=False: embed nguyên câu hỏi như bài báo (mặc định của thực nghiệm)."""

  def __init__(self, embedder, store, top_k: int = 10, clean: bool = False):
    self.embedder = embedder
    self.store = store
    self.top_k = top_k
    self.clean = clean

  def retrieve(self, question: str, process_filter: ProcessFilter = None,
               top_k: int = 0) -> List[Dict[str, Any]]:
    text = clean_query(question) if self.clean else question
    return self.store.search_top_k(self.embedder.encode(text), top_k=top_k or self.top_k,
                                   process_filter=process_filter)
