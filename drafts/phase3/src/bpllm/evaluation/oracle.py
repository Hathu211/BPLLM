"""Oracle: chấm câu trả lời yes/no của LLM và tính accuracy.

Đầu vào là file JSONL, mỗi dòng có 'expected' (đáp án đúng) và 'answer' (nguyên văn
câu trả lời của model). Chỉ dùng thư viện chuẩn để chạy được cả trên Colab.

Chạy:  python oracle.py food_delivery_top10_answers.jsonl [file khác ...]
"""
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

_YES_NO = re.compile(r"\b(yes|no)\b", re.IGNORECASE)


def extract_answer(text: str) -> Optional[str]:
  """'yes' hoặc 'no' xuất hiện đầu tiên trong câu trả lời; None nếu không có."""
  match = _YES_NO.search(text or "")
  return match.group(1).lower() if match else None


def grade(records: List[Dict[str, Any]]) -> Dict[str, Any]:
  """Chấm từng câu. Câu không rút được yes/no tính là sai và được đếm riêng."""
  total = {"yes": 0, "no": 0}
  correct = {"yes": 0, "no": 0}
  wrong, unparsed = [], []
  for i, record in enumerate(records, 1):
    qid = record.get("id", i)
    expected = str(record["expected"]).strip().lower()
    predicted = extract_answer(record.get("answer", ""))
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


def evaluate_file(path) -> Dict[str, Any]:
  """Đọc file JSONL câu trả lời, in kết quả và trả về báo cáo."""
  lines = Path(path).read_text(encoding="utf-8").splitlines()
  report = grade([json.loads(line) for line in lines if line.strip()])
  print(f"{Path(path).name}: accuracy {report['accuracy']:.2%} "
        f"({report['correct']}/{report['total']}), "
        f"yes {report['accuracy_yes']:.2%}, no {report['accuracy_no']:.2%}")
  print(f"  Sai: {report['wrong_ids']}")
  print(f"  Không rút được yes/no: {report['unparsed_ids']}")
  return report


if __name__ == "__main__":
  if len(sys.argv) < 2:
    sys.exit(__doc__)
  for answers_file in sys.argv[1:]:
    evaluate_file(answers_file)
