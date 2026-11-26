"""Khuôn prompt duy nhất của dự án.

YES/NO: khuôn Hình 4 bài báo (câu lệnh, top-k chunk, câu hỏi), gửi như một tin nhắn `user`
qua chat template của Llama 3.1. Đây là khuôn đã dùng cho lần chạy Kaggle 94,23% / 100%.
scripts/retrieve_top_k.py ghi sẵn prompt này vào file input, notebook gửi nguyên văn, nên
lúc chấm điểm và lúc chạy app dùng cùng một khuôn.

NEXT_STEP: mở rộng cho câu hỏi "sau bước X là bước gì" trên Streamlit; không dùng để chấm điểm.
"""
from typing import Dict, List, Optional, Sequence

YESNO_INSTRUCTION = ("Use the following pieces of context to answer the question at the end.\n"
                     "Answer 'yes' if true or 'no' if false.")

NEXT_STEP_INSTRUCTION = (
    "Use the following pieces of context to answer the question at the end.\n"
    "The user may describe a step in their own words instead of its exact name; match it to the "
    "step in the context with the same meaning.\n"
    "Name the step or steps that come directly after it, using the exact names written in the "
    "context. If the next element is a decision, give each branch with its condition. "
    "Answer in one or two sentences, in the same language as the question.")

INSTRUCTIONS = {"yesno": YESNO_INSTRUCTION, "next_step": NEXT_STEP_INSTRUCTION}


def build_context(chunks: Sequence[str]) -> str:
  """Ghép các chunk theo thứ tự điểm, cách nhau một dòng trống."""
  return "\n\n".join(chunks)


def build_prompt(question: str, chunks: Sequence[str], kind: str = "yesno",
                 focus: Optional[str] = None) -> str:
  """focus: tên bước app đã nhận diện từ câu hỏi (chỉ dùng cho next_step; yes/no giữ khuôn bài báo)."""
  if kind not in INSTRUCTIONS:
    raise ValueError(f"kind phải là một trong {list(INSTRUCTIONS)}")
  hint = f'\n(The question is about the step "{focus}".)' if focus and kind == "next_step" else ""
  return f"{INSTRUCTIONS[kind]}\n\n{build_context(chunks)}\n\nQuestion: {question}{hint}"


def to_messages(prompt: str) -> List[Dict[str, str]]:
  """Một tin nhắn user, mỗi câu hỏi độc lập (không có lịch sử hội thoại)."""
  return [{"role": "user", "content": prompt}]
