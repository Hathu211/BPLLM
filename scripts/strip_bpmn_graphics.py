"""Xem thử bước làm sạch BPMN gốc, KHÔNG thuộc pipeline chính.

data/raw/original/<pid>.bpmn  ->  data/processed/_preview/<pid>.bpmn

Chạy:  python scripts/strip_bpmn_graphics.py
Không sửa data/raw/, data/raw/original/ và data/processed/<pid>/. Exit code 1 nếu có file lỗi.
R8: ghi vào _preview/ để không làm lệch <pid>.bpmn với graph.json do prepare_processes.py sinh.
"""
import sys
import xml.etree.ElementTree as ET

from bpllm.config import PROJECT_ROOT
from bpllm.parsing import BpmnFormatError, strip_graphics_file

ORIGINAL_DIR = PROJECT_ROOT / "data" / "raw" / "original"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
PREVIEW_SUBDIR = "_preview"


def main() -> int:
  files = sorted(ORIGINAL_DIR.glob("*.bpmn"))
  if not files:
    print(f"Không tìm thấy file .bpmn trong {ORIGINAL_DIR}")
    return 1

  all_ok = True
  for src in files:
    pid = src.stem.lower()
    dst = PROCESSED_DIR / PREVIEW_SUBDIR / f"{pid}.bpmn"
    try:
      removed = strip_graphics_file(src, dst)
    except (ET.ParseError, BpmnFormatError) as ex:   # R2
      all_ok = False
      print(f"[LỖI] {src.name}: {ex}")
      continue
    before, after = src.stat().st_size, dst.stat().st_size
    print(f"[OK ] {pid}: {before} -> {after} bytes, đã bỏ {dict(sorted(removed.items()))}")
  return 0 if all_ok else 1


if __name__ == "__main__":
  sys.stdout.reconfigure(encoding="utf-8", errors="replace")
  sys.exit(main())
