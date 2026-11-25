"""Tra graph.json để đối chiếu câu trả lời "bước tiếp theo" của LLM với mô hình BPMN."""
import re
from functools import lru_cache
from typing import Dict, List, Optional

from bpllm.config import PROCESSED_DIR
from bpllm.parsing import Node, ProcessGraph, normalize_name


@lru_cache(maxsize=None)
def load_graph(process_id: str) -> ProcessGraph:
  path = PROCESSED_DIR / process_id / "graph.json"
  if not path.is_file():
    raise FileNotFoundError(f"Chưa có {path}. Chạy scripts/prepare_processes.py trước.")
  return ProcessGraph.load(path)


# Từ hỏi / từ nối không mang nghĩa của bước (tiếng Anh và tiếng Việt)
STOPWORDS = {
    "a", "an", "the", "to", "of", "and", "or", "in", "on", "at", "for", "by", "with", "from", "is",
    "are", "be", "been", "was", "were", "it", "its", "this", "that", "there", "what", "which", "who",
    "when", "where", "how", "why", "happen", "happens", "happened", "come", "comes", "next", "step",
    "steps", "after", "following", "follows", "follow", "then", "do", "does", "did", "done", "i",
    "we", "you", "they", "he", "she", "my", "our", "your", "their", "me", "us", "process", "activity",
    "task", "event", "once", "has", "have", "had", "can", "will", "should", "would", "please", "tell",
    "sau", "khi", "bước", "là", "gì", "thì", "tiếp", "theo", "của", "và", "có", "không", "nào",
    "quy", "trình", "kế", "đó", "rồi", "xảy", "ra", "cái",
}
# Câu "sau X thì ..." : phần sau các từ này là bước được hỏi
_FOCUS = re.compile(r"\b(after|following|once|sau khi|sau bước|sau sự kiện|sau hoạt động|sau)\b",
                    re.IGNORECASE)
TOKEN_MATCH = 0.5        # tỷ lệ từ của tên bước phải có trong câu hỏi
EMBED_MATCH = 0.45       # cosine tối thiểu khi so nghĩa bằng embedding


def _stem(word: str) -> str:
  """approve/approved/approves -> approv; register/registered -> register; checking -> check."""
  for suffix in ("ing", "ed", "es", "s"):
    if len(word) > len(suffix) + 2 and word.endswith(suffix):
      word = word[:-len(suffix)]
      break
  return word[:-1] if len(word) > 3 and word.endswith("e") else word


def tokens(text: str) -> set:
  """Từ có nghĩa, chữ thường, bỏ đuôi -s/-ed/-ing ('sent' và 'send' vẫn khác nhau)."""
  words = re.findall(r"\w+", normalize_name(text).lower())
  return {_stem(w) for w in words if w not in STOPWORDS and len(w) > 1}


def focus_text(question: str) -> str:
  """Phần câu hỏi nói về bước được hỏi: sau từ 'after'/'sau' cuối cùng, nếu có."""
  parts = _FOCUS.split(question)
  tail = (parts[-1] if len(parts) > 1 else question).strip()
  return tail if tokens(tail) else question.strip()


def _contains(text: str, phrase: str) -> bool:
  return bool(phrase) and re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


def find_mentioned_node(graph: ProcessGraph, question: str, embedder=None) -> Optional[Node]:
  """Bước được hỏi, KHÔNG cần ngoặc kép. Thử lần lượt:

  1. tên/id trong ngoặc kép (nếu người dùng có viết);
  2. tên hoặc id xuất hiện nguyên văn (không phân biệt hoa thường), lấy tên dài nhất;
  3. trùng từ: tên bước có nhiều từ nhất nằm trong phần câu sau 'after'/'sau';
  4. so nghĩa bằng embedding (nếu có embedder), ví dụ 'pay the courier' ~ 'pay rider'.
  """
  for quoted in re.findall(r'"([^"]+)"|“([^”]+)”', question):
    node = graph.find(next(q for q in quoted if q))
    if node is not None:
      return node

  focus = focus_text(question)
  for text in (focus, question):
    lowered = f" {normalize_name(text).lower()} "
    exact = [(len(key), n) for n in graph.nodes.values()
             for key in {n.name.lower(), n.id.lower()} - {""}
             if len(key) >= 3 and _contains(lowered, key)]
    if exact:
      return max(exact, key=lambda x: x[0])[1]

  wanted = tokens(focus)
  best, best_score = None, (0.0, 0)
  for node in graph.nodes.values():
    name_tokens = tokens(node.name)
    if not name_tokens or not wanted:
      continue
    hit = len(name_tokens & wanted)
    score = (hit / len(name_tokens), hit)
    if hit and score > best_score:
      best, best_score = node, score
  coverage, hits = best_score
  # Khớp chắc: đủ cả tên, hoặc >= một nửa tên và >= 2 từ. Trùng đúng 1 từ (vd chỉ 'rider') thì
  # nhường cho so nghĩa, vì 'the rider says no' gần 'the rider refused the order' hơn 'pay rider'.
  if best is not None and (coverage == 1.0 or (coverage >= TOKEN_MATCH and hits >= 2)):
    return best

  if embedder is not None:
    named = [n for n in graph.nodes.values() if n.name]
    vectors = embedder.encode([focus] + [n.name for n in named])
    query, names = vectors[0], vectors[1:]
    scores = [sum(a * b for a, b in zip(query, v)) for v in names]
    top = max(range(len(named)), key=scores.__getitem__)
    if scores[top] >= EMBED_MATCH:
      return named[top]
  return best   # trùng từ yếu vẫn hơn không có gì; None nếu không trùng từ nào


def mentioned_names(graph: ProcessGraph, question: str, embedder=None) -> List[str]:
  """Mọi tên bước xuất hiện nguyên văn trong câu hỏi; không có thì bước gần nghĩa nhất."""
  text = f" {normalize_name(question).lower()} "
  names = [n.display_name for n in graph.nodes.values()
           if n.name and len(n.name) >= 3 and _contains(text, n.name.lower())]
  if not names:
    node = find_mentioned_node(graph, question, embedder)
    names = [node.display_name] if node is not None else []
  return names


def next_steps(graph: ProcessGraph, node_id: str) -> List[Dict[str, str]]:
  """Các phần tử đi ngay sau node_id. Gateway được đi xuyên qua, giữ tên gateway và nhãn nhánh.

  Mỗi phần tử: {"id", "name", "condition", "decision"} (decision = tên/id gateway đi qua, nếu có).
  """
  result: List[Dict[str, str]] = []
  seen = set()

  def walk(source: str, condition: str, decision: str) -> None:
    for flow in graph.flows:
      if flow.source != source:
        continue
      target = graph.nodes[flow.target]
      cond = flow.name or condition
      if target.kind == "gateway" and target.id not in seen:
        seen.add(target.id)
        # Gateway có tên là một quyết định ("is the customer registered?"); không tên thì bỏ qua
        walk(target.id, cond, target.name or decision)
      elif target.kind != "gateway":
        item = {"id": target.id, "name": target.display_name, "condition": cond,
                "decision": decision}
        if item not in result:
          result.append(item)

  walk(node_id, "", "")
  return result


def mentioned_steps(answer: str, steps: List[Dict[str, str]]) -> List[str]:
  """Bước tiếp theo (theo graph) mà câu trả lời có nhắc: nguyên văn tên, hoặc đủ ~3/4 số từ của
  tên (model hay diễn đạt lại, ví dụ 'the rider accepts the order')."""
  text = normalize_name(answer).lower()
  said = tokens(answer)
  result = []
  for s in steps:
    name_tokens = tokens(s["name"])
    if _contains(text, s["name"].lower()) or (
        name_tokens and len(name_tokens & said) / len(name_tokens) >= 0.75):
      result.append(s["name"])
  return result
