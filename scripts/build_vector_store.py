"""Phase 3: chunk BPMN đã làm sạch rồi nạp vào Qdrant, mỗi kiểu chunk một collection cố định.

  specific -> QDRANT_COLLECTION_SPECIFIC (mặc định bpllm2_specific), như bài báo
  enriched -> QDRANT_COLLECTION_ENRICHED (mặc định bpllm2_enriched), phần mở rộng

Cả 3 quy trình nằm chung một collection; khi truy xuất thì lọc theo process_id.
Tên collection suy ra từ kiểu chunk, nên không thể nạp nhầm loại chunk vào collection.

Chạy:  python scripts/build_vector_store.py                       (cả hai collection)
       python scripts/build_vector_store.py --chunking enriched   (chỉ một)
Collection được tạo lại mỗi lần chạy.
"""
import argparse
import sys

from bpllm.chunking.chunking_processor import (CHUNKS_FILE, ENRICHED_CHUNKS_FILE, chunk_all,
                                               write_jsonl)
from bpllm.config import CHUNKINGS, get_settings
from bpllm.embeddings.embedder import ProcessEmbedder
from bpllm.vectorstore.qdrant_store import QdrantVectorStore


def build(chunking: str, embedder: ProcessEmbedder) -> int:
  enrich = chunking == "enriched"
  chunks = chunk_all(enrich=enrich)
  if not chunks:
    print("Không có chunk nào. Chạy scripts/prepare_processes.py trước.")
    return 1
  write_jsonl(chunks, ENRICHED_CHUNKS_FILE if enrich else CHUNKS_FILE)
  counts = {}
  for c in chunks:
    counts[c["metadata"]["process_id"]] = counts.get(c["metadata"]["process_id"], 0) + 1

  collection = get_settings().collection(chunking)
  texts = [c["text"] for c in chunks]
  store = QdrantVectorStore(collection)
  store.init_collection(vector_size=embedder.vector_size, recreate=True)
  store.upsert_chunks(texts, embedder.encode(texts), [c["metadata"] for c in chunks])

  stored, kind = store.count(), store.chunking()
  if stored != len(chunks) or kind != chunking:
    print(f"[LỖI] {collection}: có {stored} điểm kiểu '{kind}', mong đợi {len(chunks)} kiểu '{chunking}'")
    return 1
  print(f"[OK ] {collection}: {stored} chunk '{chunking}' {counts}")
  return 0


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
  parser.add_argument("--chunking", choices=[*CHUNKINGS, "both"], default="both")
  args = parser.parse_args()
  embedder = ProcessEmbedder()
  chunkings = CHUNKINGS if args.chunking == "both" else (args.chunking,)
  return max(build(c, embedder) for c in chunkings)


if __name__ == "__main__":
  sys.stdout.reconfigure(encoding="utf-8", errors="replace")
  sys.exit(main())
