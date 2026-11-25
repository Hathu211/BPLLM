"""Lấy top-k chunk cho một câu hỏi và dựng prompt gửi LLM.

Dùng chung cho Streamlit, scripts/retrieve_top_k.py và notebook Colab, để
prompt lúc demo, lúc chấm điểm và lúc fine-tune có cùng một khuôn.
"""
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from bpllm.config import PROJECT_ROOT
from bpllm.parsing import PROCESS_NAMES
from bpllm.vectorstore.qdrant_store import DEFAULT_TOP_K

# Cùng câu lệnh với scripts/prepare_dataset.py
INSTRUCTION = (
    "Use the following pieces of context to answer the question at the end. "
    "Answer 'yes' if true or 'no' if false. "
    "Also reference the corresponding piece of provided context if present."
)

# Câu lệnh cho chatbot: trả lời bằng ngôn ngữ tự nhiên, có một dòng suy luận trước.
CHAT_INSTRUCTION = (
    "You are a helpful assistant for people who take part in a business process, "
    "such as customers and employees. They do not know BPMN or process modelling.\n"
    "How to read the context: each element is one step of the process. Its <outgoing target=...> "
    "gives the step that comes next, and its <incoming source=...> gives the step that comes before. "
    "If a target or source is a gateway id, find the element with that id and follow it to the real step.\n"
    "The user often describes a situation in everyday words that do not match any step name. "
    "In that case, work out which steps in the context correspond to that situation from the meaning "
    "of their names, and explain when those steps happen in the process.\n"
    "Reply in exactly this format:\n"
    "Reasoning: <one or two short lines: which steps in the context are relevant and how they are connected>\n"
    "Answer: <the answer for the user>\n"
    "Rules for the Answer:\n"
    "- Answer directly in the first sentence, in plain everyday language, from the user's point of view.\n"
    "- Use only steps and connections that are written in the context. Never invent a step. "
    "Say you do not know only when no step in the context relates to the question.\n"
    "- Write step names in double quotes, exactly as they appear.\n"
    "- Never use the words gateway, node, flow, BPMN or XML, and never show an id.\n"
    "- Use at most three sentences unless the user asks for the whole process.\n"
    "- Answer in the same language as the question."
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


def build_chat_messages(question: str, results: List[Dict[str, Any]],
                        history: Optional[List[Dict[str, str]]] = None) -> List[Dict[str, str]]:
  """Tin nhắn gửi LLM cho chatbot: câu lệnh kèm context, lịch sử hội thoại, câu hỏi mới."""
  system = f"{CHAT_INSTRUCTION}\n\nContext BPMN:\n{build_context(results)}"
  return [{"role": "system", "content": system}, *(history or []),
          {"role": "user", "content": question}]


def split_answer(text: str) -> Tuple[str, str]:
  """Tách phần suy luận (cho Admin) và câu trả lời (cho người dùng)."""
  reasoning, marker, answer = text.partition("Answer:")
  if not marker:
    return "", text.strip()
  return reasoning.replace("Reasoning:", "", 1).strip(), answer.strip()


def process_profiles(embedder) -> Dict[str, Any]:
  """Vector đại diện mỗi quy trình: embedding của danh sách activity."""
  return {
      process_id: embedder.encode(
          (PROJECT_ROOT / "data" / "processed" / process_id / "dfg_activities.txt")
          .read_text(encoding="utf-8"))
      for process_id in PROCESS_NAMES
  }


def guess_process(question_vector, profiles: Dict[str, Any]) -> str:
  """Quy trình có hồ sơ gần câu hỏi nhất (cosine; vector đã chuẩn hóa)."""
  return max(profiles, key=lambda process_id: float(np.dot(question_vector, profiles[process_id])))


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