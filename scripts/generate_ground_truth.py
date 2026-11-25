"""Phase 1, bước 3: sinh ground truth từ graph.

data/processed/<pid>/graph.json  ->  data/ground_truth/<pid>.json

Chạy trước:  python scripts/prepare_processes.py
Chạy:        python scripts/generate_ground_truth.py
Kiểm tra:    python scripts/generate_ground_truth.py --check   (không ghi file)

Exit code 1 nếu graph thiếu hoặc không hợp lệ, hoặc nếu --check thấy file đã lệch.
File của quy trình lỗi được giữ nguyên, không bị ghi đè.
"""
import argparse
import json
import sys

from bpllm.config import PROJECT_ROOT
from bpllm.parsing import PROCESS_NAMES, ProcessGraph, build_ground_truth

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
GROUND_TRUTH_DIR = PROJECT_ROOT / "data" / "ground_truth"


def main(argv=None) -> int:
  parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
  parser.add_argument("--check", action="store_true", help="chỉ so sánh, không ghi file")
  args = parser.parse_args(argv)

  found = {p.parent.name for p in PROCESSED_DIR.glob("*/graph.json")}
  all_ok = True
  for pid in sorted(found | set(PROCESS_NAMES)):
    path = PROCESSED_DIR / pid / "graph.json"
    if not path.exists():
      all_ok = False
      print(f"[LỖI] {pid}: chưa có {path}, hãy chạy prepare_processes.py")
      continue
    graph = ProcessGraph.load(path)
    errors = graph.validate()
    if errors:
      all_ok = False
      print(f"[LỖI] {pid}: graph không hợp lệ, giữ nguyên ground truth cũ: {errors}")
      continue

    data = build_ground_truth(graph)
    target = GROUND_TRUTH_DIR / f"{pid}.json"
    if args.check:
      current = json.loads(target.read_text(encoding="utf-8")) if target.exists() else None
      same = current == data
      all_ok = all_ok and same
      print(f"[{'OK ' if same else 'LỆCH'}] {pid}")
      continue
    GROUND_TRUTH_DIR.mkdir(parents=True, exist_ok=True)
    # R9: newline="\n" để file đã commit không đổi khi sinh lại trên Windows
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8", newline="\n")
    print(f"[OK ] {pid}: {len(data['activities'])} activity, {len(data['gateways'])} gateway,"
          f" {len(data['sequence_flows'])} flow")
  return 0 if all_ok else 1


if __name__ == "__main__":
  sys.stdout.reconfigure(encoding="utf-8", errors="replace")
  sys.exit(main())
