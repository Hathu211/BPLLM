"""Phase 6: chấm mọi file câu trả lời trong data/results/ và lập bảng so sánh.

Tải các file answers_<thực nghiệm>_<chunk>_<quant>.jsonl từ Output của notebook Kaggle vào
data/results/, rồi chạy:
  python scripts/evaluate.py
Ghi data/results/summary.json và data/results/summary.md.
"""
import json
import re
import sys

from bpllm.config import RESULTS_DIR
from bpllm.evaluation.oracle import grade, read_jsonl
from bpllm.experiments import EXPERIMENTS, MODEL_GROUPS

_NAME = re.compile(r"^answers_(?P<exp>.+)_(?P<chunk>specific|enriched)_(?P<quant>int4|int8)\.jsonl$")


def main() -> int:
  rows = []
  for path in sorted(RESULTS_DIR.glob("answers_*.jsonl")):
    m = _NAME.match(path.name)
    if not m or m["exp"] not in EXPERIMENTS:
      print(f"[BỎ QUA] {path.name}: tên không theo mẫu answers_<thực nghiệm>_<chunk>_<quant>.jsonl")
      continue
    exp = EXPERIMENTS[m["exp"]]
    report = grade(read_jsonl(path))
    if report["total"] != exp.expected_count:
      print(f"[CẢNH BÁO] {path.name}: {report['total']} câu, mong đợi {exp.expected_count}")
    rows.append({"file": path.name, "experiment": exp.name, "chunking": m["chunk"],
                 "quant": m["quant"], "model": MODEL_GROUPS[exp.model_group].model(m["quant"]),
                 **report})
  if not rows:
    print(f"Chưa có file answers_*.jsonl trong {RESULTS_DIR}")
    return 1

  lines = ["| Thực nghiệm | Model | Chunk | Accuracy | Đúng | Yes | No | Không rút được |",
           "| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: |"]
  for r in rows:
    lines.append(f"| {r['experiment']} | {r['model']} | {r['chunking']} | {r['accuracy']:.2%} | "
                 f"{r['correct']}/{r['total']} | {r['accuracy_yes']:.2%} | {r['accuracy_no']:.2%} | "
                 f"{len(r['unparsed_ids'])} |")
  table = "\n".join(lines)
  print(table)
  (RESULTS_DIR / "summary.md").write_text(table + "\n", encoding="utf-8", newline="\n")
  (RESULTS_DIR / "summary.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n",
                                            encoding="utf-8", newline="\n")
  print(f"Đã ghi {RESULTS_DIR / 'summary.md'} và summary.json")
  return 0


if __name__ == "__main__":
  sys.stdout.reconfigure(encoding="utf-8", errors="replace")
  sys.exit(main())
