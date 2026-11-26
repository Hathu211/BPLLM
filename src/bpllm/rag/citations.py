"""Trích dẫn nguồn: những chunk BPMN mà câu trả lời dựa vào."""
import re
from typing import Any, Dict, Iterable, List, Optional

from bpllm.parsing import normalize_name


def _contains(text: str, phrase: str) -> bool:
  """phrase xuất hiện nguyên cụm (không khớp giữa một từ khác)."""
  return bool(phrase) and re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


def _mentioned(meta: Dict[str, Any], text: str) -> bool:
  name = normalize_name(meta.get("node_name")).lower()
  node_id = (meta.get("node_id") or "").lower()
  return _contains(text, name) or _contains(text, node_id)


def cite(results: List[Dict[str, Any]], answer: str, question: str = "",
         fallback: int = 3, must_include: Optional[str] = None,
         names: Iterable[str] = ()) -> List[Dict[str, Any]]:
  """Chunk có tên/id được nhắc trong câu trả lời hoặc câu hỏi; không có thì lấy `fallback` chunk đầu.

  must_include: node_id luôn được trích (ví dụ bước được hỏi ở câu "bước tiếp theo").
  names: tên bước app đã nhận diện từ graph (người dùng không cần viết đúng tên hay ngoặc kép).
  """
  text = normalize_name(f"{answer} {question}").lower()
  ranked = [dict(rank=i, **r) for i, r in enumerate(results, 1)]
  wanted = {normalize_name(n).lower() for n in names if n}
  wanted |= {normalize_name(q).lower() for q in re.findall(r'"([^"]+)"', f"{answer} {question}")}
  wanted.discard("")
  # Tên không có chunk riêng trong top-k: tìm trong nội dung chunk khác, ví dụ chunk enriched
  # <outgoing target="Approve expense report"> của gateway đứng trước bước đó.
  own = {normalize_name(r["metadata"].get("node_name")).lower() for r in ranked}
  attributes = {f'"{name}"' for name in wanted - own}
  cited = [r for r in ranked if _mentioned(r["metadata"], text)
           or normalize_name(r["metadata"].get("node_name")).lower() in wanted
           or any(a in r["content"].lower() for a in attributes)
           or (must_include and r["metadata"].get("node_id") == must_include)]
  chosen = cited or ranked[:fallback]
  return [{"rank": r["rank"], "score": round(r["score"], 4),
           "process_id": r["metadata"].get("process_id", ""),
           "node_id": r["metadata"].get("node_id", ""),
           "node_name": r["metadata"].get("node_name", ""),
           "node_type": r["metadata"].get("node_type", ""),
           "text": r["content"]}
          for r in chosen]
