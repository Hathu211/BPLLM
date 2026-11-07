"""R4 (tiêu chí C15): đếm số token của mọi biểu diễn mà Phase 1 sinh ra.

Chạy trên Google Colab/Kaggle (máy local không cài transformers):
    !pip install "transformers>=4.43,<5"
    from huggingface_hub import login; login()          # Llama 3.1 cần chấp nhận license trên HF
    !python scripts/count_tokens.py
    !python scripts/count_tokens.py --model meta-llama/Llama-2-13b-chat-hf

Đọc  data/processed/<pid>/{<pid>.bpmn, dfg_activities.txt, dfg_flows_*.txt}
Ghi  data/processed/token_counts.json   (gộp kết quả của nhiều model, khóa theo tên model)
"""
import argparse
import json
import sys

from bpllm.config import PROJECT_ROOT

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DEFAULT_MODEL = "meta-llama/Llama-3.1-8B-Instruct"
CONTEXT_WINDOW = {"meta-llama/Llama-3.1-8B-Instruct": 131072,
                  "meta-llama/Llama-2-13b-chat-hf": 4096,
                  "meta-llama/Llama-2-7b-chat-hf": 4096}
FILES = ["{pid}.bpmn", "dfg_activities.txt", "dfg_flows_paper.txt",
         "dfg_flows_full.txt", "dfg_flows_gateway.txt"]


def count(tokenizer, text: str) -> int:
  return len(tokenizer(text, add_special_tokens=False)["input_ids"])


def main(argv=None) -> int:
  parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
  parser.add_argument("--model", default=DEFAULT_MODEL)
  args = parser.parse_args(argv)

  try:
    from transformers import AutoTokenizer
  except ImportError:
    print("Thiếu transformers. Script này chạy trên Colab/Kaggle, xem docstring.")
    return 1
  tokenizer = AutoTokenizer.from_pretrained(args.model)

  pids = sorted(p.parent.name for p in PROCESSED_DIR.glob("*/graph.json"))
  if not pids:
    print(f"Chưa có graph trong {PROCESSED_DIR}, hãy chạy prepare_processes.py")
    return 1

  limit = CONTEXT_WINDOW.get(args.model)
  result = {}
  for pid in pids:
    result[pid] = {}
    for pattern in FILES:
      path = PROCESSED_DIR / pid / pattern.format(pid=pid)
      if path.exists():
        n = count(tokenizer, path.read_text(encoding="utf-8"))
        result[pid][path.name] = n
        warn = f"  (vượt context {limit})" if limit and n > limit else ""
        print(f"{pid:15} {path.name:24} {n:7d}{warn}")

  out = PROCESSED_DIR / "token_counts.json"
  data = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
  data[args.model] = {"context_window": limit, "counts": result}
  out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
  print(f"Đã ghi {out}")
  return 0


if __name__ == "__main__":
  sys.stdout.reconfigure(encoding="utf-8", errors="replace")
  sys.exit(main())
