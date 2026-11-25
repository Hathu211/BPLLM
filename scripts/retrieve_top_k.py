"""Lấy top-10 chunk cho từng câu hỏi benchmark, xuất JSONL để chạy LLM trên Colab.

Chạy (Qdrant phải đang bật và đã chạy build_vector_store.py):
  python scripts/retrieve_top_k.py
  python scripts/retrieve_top_k.py --process food_delivery --top-k 10 --clean-query
  python scripts/retrieve_top_k.py --no-filter        (tìm trên mọi quy trình, như Bảng 4 bài báo)
  python scripts/retrieve_top_k.py --collection bpllm_processes_enriched --out data/rag_inputs/food_delivery_top10_enriched.jsonl

Mỗi dòng output: id, question, expected, process_id, top_k, instruction, input, contexts.
'instruction' + 'input' là prompt gửi LLM; 'expected' để oracle chấm điểm.
"""
import argparse
import json
from pathlib import Path

import pandas as pd

from bpllm.config import PROJECT_ROOT
from bpllm.embeddings.embedder import ProcessEmbedder
from bpllm.rag.retriever import INSTRUCTION, Retriever, build_input
from bpllm.vectorstore.qdrant_store import DEFAULT_TOP_K, QdrantVectorStore

DEFAULT_QUESTIONS = PROJECT_ROOT / "data" / "questions" / "3_questions_answers_refined.csv"
DEFAULT_OUT_DIR = PROJECT_ROOT / "data" / "rag_inputs"


def main() -> None:
  parser = argparse.ArgumentParser(description=__doc__,
                                   formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
  parser.add_argument("--process", default="food_delivery",
                      help="process_id dùng để lọc (mặc định food_delivery)")
  parser.add_argument("--no-filter", action="store_true", help="không lọc theo quy trình")
  parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
  parser.add_argument("--clean-query", action="store_true",
                      help="bỏ câu lệnh lặp lại trước khi embed câu hỏi")
  parser.add_argument("--collection", default=None,
                      help="tên collection Qdrant; mặc định lấy QDRANT_COLLECTION")
  parser.add_argument("--out", type=Path, default=None)
  args = parser.parse_args()

  process_filter = None if args.no_filter else args.process
  tag = "all" if args.no_filter else args.process
  out = args.out or DEFAULT_OUT_DIR / f"{tag}_top{args.top_k}.jsonl"

  df = pd.read_csv(args.questions)
  q_col = "question" if "question" in df.columns else df.columns[0]
  a_col = "answer" if "answer" in df.columns else df.columns[-1]

  retriever = Retriever(ProcessEmbedder(), QdrantVectorStore(collection_name=args.collection),
                        top_k=args.top_k, clean=args.clean_query)

  out.parent.mkdir(parents=True, exist_ok=True)
  with out.open("w", encoding="utf-8") as f:
    for i, row in enumerate(df.itertuples(index=False), 1):
      question = str(getattr(row, q_col)).strip()
      results = retriever.retrieve(question, process_id=process_filter)
      record = {
          "id": i,
          "question": question,
          "expected": str(getattr(row, a_col)).strip().lower(),
          "process_id": process_filter,
          "top_k": args.top_k,
          "instruction": INSTRUCTION,
          "input": build_input(question, results, args.process),
          "contexts": [
              {"rank": r, "score": round(hit["score"], 4),
               "process_id": hit["metadata"].get("process_id"),
               "node_id": hit["metadata"].get("node_id"),
               "node_name": hit["metadata"].get("node_name"),
               "text": hit["content"]}
              for r, hit in enumerate(results, 1)
          ],
      }
      f.write(json.dumps(record, ensure_ascii=False) + "\n")

  print(f"Đã ghi {len(df)} câu hỏi (top-{args.top_k}, filter={process_filter}) vào {out}")


if __name__ == "__main__":
  main()
