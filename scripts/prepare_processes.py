"""Phase 1, bước 2: chuẩn hóa quy trình.

data/raw/original/<pid>.bpmn (nếu chưa có thì dùng data/raw/<pid>.bpmn)  ->  data/processed/<pid>/
    <pid>.bpmn             BPMN đã bỏ đồ họa (input cho chunking và Pure LLM)
    graph.json             node + sequence flow, nguồn sự thật cho các phase sau
    dfg_activities.txt     danh sách activity, đúng format của bài báo
    dfg_flows_paper.txt    giống file của bài: bỏ flow chạm gateway không tên
    dfg_flows_full.txt     gộp gateway không tên, không mất chuyển tiếp giữa các activity
    dfg_flows_gateway.txt  đủ mọi flow; gateway có tên gọi bằng tên, không tên gọi bằng id
data/processed/phase1_report.json

Khi có cả hai file, graph của bản gốc phải trùng với data/raw/<pid>.bpmn.

Chạy:  python scripts/prepare_processes.py   (exit code 1 nếu có quy trình không hợp lệ)
"""
import json
import sys
import xml.etree.ElementTree as ET

from bpllm.config import PROJECT_ROOT
from bpllm.parsing import (BpmnFormatError, activities_text, clean_bpmn, flows_text, parse_bpmn,
                           parse_bpmn_text)

RAW_DIR = PROJECT_ROOT / "data" / "raw"
ORIGINAL_DIR = RAW_DIR / "original"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


def process_one(pid, src, baseline):
  """Trả về (report, kết quả cần ghi). Chưa ghi gì để file lỗi không để lại kết quả dở."""
  report = {"source": src.name, "from_original": src.parent == ORIGINAL_DIR,
            "counts": {}, "errors": [], "warnings": [], "removed": {}, "renamed": []}
  try:
    result = clean_bpmn(src.read_text(encoding="utf-8"))
    cleaned, removed = result.text, result.removed
    graph = parse_bpmn_text(cleaned, pid, f"{pid}.bpmn")
    errors = graph.validate()
    if baseline is not None and baseline != src:
      errors += graph.diff(parse_bpmn(baseline, pid))
  except (ET.ParseError, BpmnFormatError) as ex:
    report["errors"] = [str(ex)]
    return report, None

  gateways = graph.by_kind("gateway")
  report.update(
      counts=graph.counts(), errors=errors, warnings=graph.warnings(),
      removed=dict(sorted(removed.items())),
      renamed=result.renamed,   # R10: tên gốc trước khi chuẩn hóa khoảng trắng
      gateways={"named": sum(n.lookup == "name" for n in gateways),
                "unnamed": sum(n.lookup == "id" for n in gateways)},
  )
  return report, None if errors else (graph, cleaned)


def _write(path, text):
  # R9: newline="\n" để output giống hệt nhau trên Windows và Colab/Kaggle
  path.write_text(text, encoding="utf-8", newline="\n")


def write_outputs(pid, graph, cleaned):
  out = PROCESSED_DIR / pid
  out.mkdir(parents=True, exist_ok=True)
  _write(out / f"{pid}.bpmn", cleaned)
  graph.save(out / "graph.json")
  _write(out / "dfg_activities.txt", activities_text(graph))
  for mode in ("paper", "full", "gateway"):
    _write(out / f"dfg_flows_{mode}.txt", flows_text(graph, mode))


def main() -> int:
  raws = {p.stem.lower(): p for p in RAW_DIR.glob("*.bpmn")}
  originals = {p.stem.lower(): p for p in ORIGINAL_DIR.glob("*.bpmn")}
  pids = sorted(set(raws) | set(originals))
  if not pids:
    print(f"Không tìm thấy file .bpmn trong {RAW_DIR}")
    return 1

  report, all_ok = {}, True
  for pid in pids:
    src = originals.get(pid) or raws[pid]
    report[pid], result = process_one(pid, src, raws.get(pid))
    if result is not None:
      write_outputs(pid, *result)
    errors, warnings = report[pid]["errors"], report[pid]["warnings"]
    all_ok = all_ok and not errors
    print(f"[{'OK ' if not errors else 'LỖI'}] {pid}: {report[pid]['counts']}")
    for err in errors:
      print(f"      - {err}")
    for warning in warnings:
      print(f"      ! {warning}")

  PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
  _write(PROCESSED_DIR / "phase1_report.json", json.dumps(report, indent=2, ensure_ascii=False) + "\n")
  print(f"Đã ghi kết quả vào {PROCESSED_DIR}")
  return 0 if all_ok else 1


if __name__ == "__main__":
  sys.stdout.reconfigure(encoding="utf-8", errors="replace")
  sys.exit(main())
