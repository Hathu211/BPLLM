"""Chunk BPMN đã làm sạch (BPMN-specific, mỗi node một chunk) rồi nạp vào Qdrant.

Chạy:  python scripts/build_vector_store.py
       python scripts/build_vector_store.py --process food_delivery   (chỉ 1 quy trình)
       python scripts/build_vector_store.py --enrich --collection bpllm_processes_enriched
Collection được tạo lại mỗi lần chạy. Dùng --collection khác nhau để giữ cả hai
index (bài báo và enrichment) cùng lúc khi chạy ablation.
"""
import argparse

from bpllm.chunking.chunking_processor import (CHUNKS_FILE, ENRICHED_CHUNKS_FILE,
                                               chunk_all, write_jsonl)
from bpllm.embeddings.embedder import ProcessEmbedder
from bpllm.vectorstore.qdrant_store import QdrantVectorStore


def main() -> None:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--process", action="append", dest="processes",
                      help="process_id cần nạp (lặp lại được); mặc định nạp tất cả")
  parser.add_argument("--enrich", action="store_true",
                      help="chunk enrichment (cải tiến) thay vì chunk như bài báo")
  parser.add_argument("--collection", default=None,
                      help="tên collection Qdrant; mặc định lấy QDRANT_COLLECTION")
  args = parser.parse_args()

  print("=" * 70)
  print(f" BUILD VECTOR STORE ({'enriched' if args.enrich else 'BPMN-specific'} chunking)")
  print("=" * 70)

  chunks = chunk_all(process_ids=args.processes, enrich=args.enrich)
  if not chunks:
    print("Không có chunk nào. Kiểm tra data/processed/<process>/<process>.bpmn.")
    return
  chunks_file = ENRICHED_CHUNKS_FILE if args.enrich else CHUNKS_FILE
  write_jsonl(chunks, chunks_file)
  counts = {}
  for c in chunks:
    pid = c["metadata"]["process_id"]
    counts[pid] = counts.get(pid, 0) + 1
  print(f"Chunks: {len(chunks)} {counts} -> {chunks_file}")

  texts = [c["text"] for c in chunks]
  metadatas = [c["metadata"] for c in chunks]

  embedder = ProcessEmbedder()
  embeddings = embedder.encode(texts)

  store = QdrantVectorStore(collection_name=args.collection)
  store.init_collection(vector_size=embedder.vector_size, recreate=True)
  store.upsert_chunks(texts, embeddings, metadatas)

  print("=" * 70)
  print(" DONE")
  print("=" * 70)


if __name__ == "__main__":
  main()
