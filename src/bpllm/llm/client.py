"""Gọi server LLM chuẩn OpenAI (notebook Kaggle) bằng thư viện `openai`.

Không gửi gì cho OpenAI: `base_url` trỏ về server của dự án. Trường `model` của request chọn
model fine-tune nào trả lời (xem bpllm.experiments.app_model).
"""
from typing import Dict, List, Optional

from openai import OpenAI

from bpllm.config import get_settings


class LLMClient:

  def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None,
               timeout: Optional[int] = None, client=None):
    settings = get_settings()
    self.base_url = base_url or settings.llm_base_url
    self.max_tokens = settings.llm_max_tokens
    self.client = client or OpenAI(base_url=self.base_url,
                                   api_key=api_key or settings.llm_api_key,
                                   timeout=timeout or settings.llm_timeout)

  def chat(self, model: str, messages: List[Dict[str, str]],
           max_tokens: Optional[int] = None) -> str:
    """Giải mã greedy (temperature 0) để kết quả lặp lại được."""
    response = self.client.chat.completions.create(
        model=model, messages=messages, temperature=0,
        max_tokens=max_tokens or self.max_tokens)
    return (response.choices[0].message.content or "").strip()

  def available_models(self) -> List[str]:
    """Các model server đang nạp."""
    return [m.id for m in self.client.models.list().data]
