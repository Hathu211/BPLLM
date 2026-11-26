"""Oracle: chấm câu trả lời yes/no của LLM và tính accuracy (như bài báo).

Đầu vào là file JSONL, mỗi dòng có 'expected' (đáp án đúng) và 'answer' (nguyên văn câu trả
lời của model). Chỉ dùng thư viện chuẩn; notebook Kaggle có bản chép của các hàm này.

Chạy:  python -m bpllm.evaluation.oracle data/results/answers_fd_ft_enriched_int4.jsonl [...]
"""
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_YES_NO = re.compile(r"\b(yes|no)\b", re.IGNORECASE)
LABELS = ("yes", "no")


def extract_answer(text: Optional[str]) -> Optional[str]:
  """'yes' hoặc 'no' xuất hiện đầu tiên trong câu trả lời; None nếu không có."""
  match = _YES_NO.search(text or "")
  return match.group(1).lower() if match else None


def grade(records: List[Dict[str, Any]]) -> Dict[str, Any]:
  """Chấm từng câu. Câu không rút được yes/no tính là sai và được đếm riêng."""
  total = {label: 0 for label in LABELS}
  correct = {label: 0 for label in LABELS}
  wrong, unparsed = [], []
  for i, record in enumerate(records, 1):
    qid = record.get("id", i)
    expected = str(record["expected"]).strip().lower()
    if expected not in LABELS:
      raise ValueError(f"câu {qid}: expected phải là yes/no, nhận được '{record['expected']}'")
    predicted = extract_answer(record.get("answer"))
    total[expected] += 1
    if predicted is None:
      unparsed.append(qid)
    if predicted == expected:
      correct[expected] += 1
    else:
      wrong.append(qid)
  n = len(records)
  return {
      "total": n,
      "correct": sum(correct.values()),
      "accuracy": sum(correct.values()) / n if n else 0.0,
      "accuracy_yes": correct["yes"] / total["yes"] if total["yes"] else 0.0,
      "accuracy_no": correct["no"] / total["no"] if total["no"] else 0.0,
      "wrong_ids": wrong,
      "unparsed_ids": unparsed,
  }


def read_jsonl(path) -> List[Dict[str, Any]]:
  lines = Path(path).read_text(encoding="utf-8").splitlines()
  return [json.loads(line) for line in lines if line.strip()]


def evaluate_file(path) -> Dict[str, Any]:
  """Đọc file JSONL câu trả lời, in kết quả và trả về báo cáo."""
  report = grade(read_jsonl(path))
  print(f"{Path(path).name}: accuracy {report['accuracy']:.2%} "
        f"({report['correct']}/{report['total']}), "
        f"yes {report['accuracy_yes']:.2%}, no {report['accuracy_no']:.2%}")
  print(f"  Sai: {report['wrong_ids']}")
  print(f"  Không rút được yes/no: {report['unparsed_ids']}")
  return report


if __name__ == "__main__":
  if len(sys.argv) < 2:
    sys.exit(__doc__)
  sys.stdout.reconfigure(encoding="utf-8", errors="replace")
  for answers_file in sys.argv[1:]:
    evaluate_file(answers_file)
