"""Phase 4: lấy top-k chunk cho từng câu hỏi của mỗi thực nghiệm, xuất JSONL cho notebook Kaggle.

Mỗi thực nghiệm (bpllm.experiments.EXPERIMENTS) x mỗi kiểu chunk ra một file
data/rag_inputs/<thực nghiệm>_<chunk>_top10.jsonl, ví dụ fd_ft_enriched_top10.jsonl.
Kho truy xuất gồm đúng các quy trình của nhóm model (Food Delivery; FD + E-commerce; FD + Reimbursement).

Mỗi dòng: id, question, expected, experiment, chunking, collection, processes, top_k,
prompt (nguyên văn gửi LLM), contexts (chunk kèm điểm, để phân tích và trích dẫn).

Chạy (Qdrant đang bật, đã chạy build_vector_store.py):
  python scripts/retrieve_top_k.py                           (mọi thực nghiệm, cả hai kiểu chunk)
  python scripts/retrieve_top_k.py --experiment fd_ft --chunking enriched
"""
import argparse
import csv
import json
import sys

from bpllm.config import CHUNKINGS, get_settings
from bpllm.embeddings.embedder import ProcessEmbedder
from bpllm.experiments import EXPERIMENTS, rag_input_path
from bpllm.rag.prompts import build_prompt
from bpllm.rag.retriever import Retriever
from bpllm.vectorstore.qdrant_store import QdrantVectorStore


def read_questions(path):
  with open(path, encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
  return [(r["question"].strip(), r["answer"].strip().lower()) for r in rows]


def run(experiment, chunking, embedder, top_k) -> int:
  collection = get_settings().collection(chunking)
  store = QdrantVectorStore(collection)
  actual = store.chunking()
  if actual != chunking:
    print(f"[LỖI] collection '{collection}' chứa chunk '{actual}', cần '{chunking}'. "
          "Chạy lại scripts/build_vector_store.py.")
    return 1
  questions = read_questions(experiment.questions_path)
  if len(questions) != experiment.expected_count:
    print(f"[LỖI] {experiment.questions_file}: {len(questions)} câu, mong đợi {experiment.expected_count}")
    return 1

  retriever = Retriever(embedder, store, top_k=top_k)
  out = rag_input_path(experiment.name, chunking, top_k)
  out.parent.mkdir(parents=True, exist_ok=True)
  with out.open("w", encoding="utf-8", newline="\n") as f:
    for i, (question, expected) in enumerate(questions, 1):
      results = retriever.retrieve(question, process_filter=list(experiment.processes))
      record = {
          "id": i, "question": question, "expected": expected,
          "experiment": experiment.name, "chunking": chunking, "collection": collection,
          "processes": list(experiment.processes), "top_k": top_k,
          "prompt": build_prompt(question, [r["content"] for r in results], "yesno"),
          "contexts": [{"rank": r, "score": round(hit["score"], 4),
                        "process_id": hit["metadata"].get("process_id"),
                        "node_id": hit["metadata"].get("node_id"),
                        "node_name": hit["metadata"].get("node_name"),
                        "text": hit["content"]}
                       for r, hit in enumerate(results, 1)],
      }
      f.write(json.dumps(record, ensure_ascii=False) + "\n")
  print(f"[OK ] {out.name}: {len(questions)} câu, kho {list(experiment.processes)}, "
        f"collection {collection}")
  return 0


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                   formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument("--experiment", choices=[*EXPERIMENTS, "all"], default="all")
  parser.add_argument("--chunking", choices=[*CHUNKINGS, "both"], default="both")
  parser.add_argument("--top-k", type=int, default=None)
  args = parser.parse_args()

  top_k = args.top_k or get_settings().top_k
  experiments = EXPERIMENTS.values() if args.experiment == "all" else [EXPERIMENTS[args.experiment]]
  chunkings = CHUNKINGS if args.chunking == "both" else (args.chunking,)
  embedder = ProcessEmbedder()
  return max(run(e, c, embedder, top_k) for e in experiments for c in chunkings)


if __name__ == "__main__":
  sys.stdout.reconfigure(encoding="utf-8", errors="replace")
  sys.exit(main())
