"""Lấy top-k chunk cho một câu hỏi và dựng prompt gửi LLM.

Dùng chung cho Streamlit, scripts/retrieve_top_k.py và notebook Colab, để
prompt lúc demo, lúc chấm điểm và lúc fine-tune có cùng một khuôn.
"""
import re
from typing import Any, Dict, List, Optional

from bpllm.parsing import PROCESS_NAMES
from bpllm.vectorstore.qdrant_store import DEFAULT_TOP_K

# Cùng câu lệnh với scripts/prepare_dataset.py
INSTRUCTION = (
    "Use the following pieces of context to answer the question at the end. "
    "Answer 'yes' if true or 'no' if false. "
    "Also reference the corresponding piece of provided context if present."
)

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


def build_context(results: List[Dict[str, Any]]) -> str:
  """Ghép các chunk theo thứ tự điểm, cách nhau một dòng trống."""
  return "\n\n".join(r["content"] for r in results)


def build_input(question: str, results: List[Dict[str, Any]],
                process_id: Optional[str] = None) -> str:
  """Phần 'input' của prompt, cùng khuôn với dữ liệu fine-tune."""
  process_name = PROCESS_NAMES.get(process_id, process_id) if process_id else "All processes"
  return (f"Process: {process_name}\n"
          f"Context BPMN:\n{build_context(results)}\n\n"
          f"Question: {question}")


class Retriever:
  """Embed câu hỏi rồi tìm top-k chunk trong Qdrant."""

  def __init__(self, embedder, store, top_k: int = DEFAULT_TOP_K, clean: bool = False):
    self.embedder = embedder
    self.store = store
    self.top_k = top_k
    self.clean = clean

  def retrieve(self, question: str, process_id: Optional[str] = None,
               top_k: Optional[int] = None) -> List[Dict[str, Any]]:
    text = clean_query(question) if self.clean else question
    vector = self.embedder.encode(text)
    return self.store.search_top_k(vector, top_k=top_k or self.top_k,
                                   process_filter=process_id)
