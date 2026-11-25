"""Luồng trả lời một câu hỏi của Streamlit (và scripts/ask.py).

1. Xác định quy trình (người dùng chọn, hoặc nhận diện từ câu hỏi).
2. Xác định loại câu hỏi: yes/no hay "bước tiếp theo".
3. Lấy top-k chunk của đúng quy trình đó (collection enriched mặc định).
4. Dựng prompt, gọi model fine-tune tương ứng với quy trình.
5. Rút yes/no (câu yes/no) hoặc đối chiếu với graph.json (câu bước tiếp theo), kèm trích dẫn.
"""
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from bpllm.config import PROCESSED_DIR, get_settings
from bpllm.evaluation.oracle import extract_answer
from bpllm.experiments import app_model
from bpllm.parsing import PROCESS_NAMES
from bpllm.rag import graph_lookup, question_type
from bpllm.rag.citations import cite
from bpllm.rag.prompts import build_prompt, to_messages


def process_profiles(embedder) -> Dict[str, Any]:
  """Vector đại diện mỗi quy trình: embedding danh sách activity của nó."""
  return {pid: embedder.encode((PROCESSED_DIR / pid / "dfg_activities.txt").read_text(encoding="utf-8"))
          for pid in PROCESS_NAMES}


def guess_process(question_vector, profiles: Dict[str, Any]) -> str:
  """Quy trình có hồ sơ gần câu hỏi nhất (cosine; vector đã chuẩn hóa)."""
  return max(profiles, key=lambda pid: float(np.dot(question_vector, profiles[pid])))


@dataclass
class Answer:
  question: str
  process_id: str
  kind: str
  model: str
  prompt: str
  text: str = ""                       # nguyên văn câu trả lời của model
  verdict: Optional[str] = None        # 'yes' / 'no' với câu yes/no
  results: List[Dict[str, Any]] = field(default_factory=list)
  citations: List[Dict[str, Any]] = field(default_factory=list)
  asked_node: Optional[Dict[str, str]] = None       # bước được hỏi (câu bước tiếp theo)
  expected_steps: List[Dict[str, str]] = field(default_factory=list)   # theo graph.json
  matched_steps: List[str] = field(default_factory=list)              # có trong câu trả lời
  names: List[str] = field(default_factory=list)      # tên bước nhận diện được từ câu hỏi (graph)
  error: Optional[str] = None

  @property
  def graph_agrees(self) -> Optional[bool]:
    """Câu bước tiếp theo: câu trả lời có nhắc đủ các bước mà graph.json chỉ ra không."""
    if self.kind != question_type.NEXT_STEP or not self.expected_steps:
      return None
    return len(self.matched_steps) == len({s["name"] for s in self.expected_steps})


class Assistant:

  def __init__(self, embedder, retriever, llm, profiles: Dict[str, Any],
               quant: Optional[str] = None,
               graph_loader: Callable = graph_lookup.load_graph):
    self.embedder = embedder
    self.retriever = retriever
    self.llm = llm
    self.profiles = profiles
    self.quant = quant or get_settings().llm_quant
    self.graph_loader = graph_loader

  def resolve_process(self, question: str, process_id: Optional[str]) -> str:
    return process_id or guess_process(self.embedder.encode(question), self.profiles)

  def prepare(self, question: str, process_id: Optional[str] = None,
              kind: Optional[str] = None) -> Answer:
    """Bước 1-4 trừ việc gọi model: dùng cho màn Admin để xem prompt."""
    pid = self.resolve_process(question, process_id)
    kind = kind or question_type.classify(question)
    results = self.retriever.retrieve(question, process_filter=pid)
    answer = Answer(question, pid, kind, app_model(pid, self.quant), "", results=results)
    graph = self.graph_loader(pid)
    if kind == question_type.NEXT_STEP:
      # Người dùng không cần viết đúng tên bước hay dùng ngoặc kép: nhận diện bằng từ và nghĩa
      node = graph_lookup.find_mentioned_node(graph, question, self.embedder)
      if node is not None:
        answer.asked_node = {"id": node.id, "name": node.display_name}
        answer.expected_steps = graph_lookup.next_steps(graph, node.id)
        answer.results = self._with_chunk_of(node, pid, results)
        answer.names = [node.display_name] + [s["name"] for s in answer.expected_steps]
    else:
      answer.names = graph_lookup.mentioned_names(graph, question, self.embedder)
    focus = answer.asked_node["name"] if answer.asked_node else None
    answer.prompt = build_prompt(question, [r["content"] for r in answer.results], kind, focus)
    return answer

  def _with_chunk_of(self, node, pid: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Câu hỏi diễn đạt khác tên bước có thể làm chunk của chính bước đó rơi khỏi top-k:
    lấy chunk đó bằng tên bước và đặt lên đầu, bỏ chunk cuối để giữ đúng k chunk."""
    if any(r["metadata"].get("node_id") == node.id for r in results):
      return results
    own = [r for r in self.retriever.retrieve(node.display_name, process_filter=pid)
           if r["metadata"].get("node_id") == node.id]
    return own[:1] + results[:len(results) - 1] if own else results

  def ask(self, question: str, process_id: Optional[str] = None,
          kind: Optional[str] = None) -> Answer:
    answer = self.prepare(question, process_id, kind)
    try:
      answer.text = self.llm.chat(answer.model, to_messages(answer.prompt))
    except Exception as error:   # mạng, tunnel hết hạn, sai API key...
      answer.error = f"{type(error).__name__}: {error}"
      return answer
    if answer.kind == question_type.YESNO:
      answer.verdict = extract_answer(answer.text)
    else:
      answer.matched_steps = graph_lookup.mentioned_steps(answer.text, answer.expected_steps)
    asked = answer.asked_node["id"] if answer.asked_node else None
    answer.citations = cite(answer.results, answer.text, question, must_include=asked,
                            names=answer.names)
    return answer
