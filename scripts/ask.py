"""Hỏi một câu qua đúng luồng của Streamlit, chạy trong terminal (để thử server Kaggle).

Chạy:  python scripts/ask.py "What happens after \"register the order\"?" --process food_delivery
       python scripts/ask.py "Is there an activity with name=\"pay rider\"?"
"""
import argparse
import sys

from bpllm.config import get_settings
from bpllm.embeddings.embedder import ProcessEmbedder
from bpllm.llm.client import LLMClient
from bpllm.parsing import PROCESS_NAMES
from bpllm.rag.assistant import Assistant, process_profiles
from bpllm.rag.question_type import KINDS
from bpllm.rag.retriever import Retriever
from bpllm.vectorstore.qdrant_store import QdrantVectorStore


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
  parser.add_argument("question")
  parser.add_argument("--process", choices=list(PROCESS_NAMES), default=None,
                      help="bỏ trống để tự nhận diện quy trình")
  parser.add_argument("--kind", choices=KINDS, default=None, help="bỏ trống để tự nhận diện")
  parser.add_argument("--dry-run", action="store_true", help="chỉ in prompt, không gọi LLM")
  args = parser.parse_args()

  settings = get_settings()
  embedder = ProcessEmbedder()
  store = QdrantVectorStore(settings.collection(settings.app_chunking))
  assistant = Assistant(embedder, Retriever(embedder, store, settings.top_k), LLMClient(),
                        process_profiles(embedder))
  if args.dry_run:
    answer = assistant.prepare(args.question, args.process, args.kind)
    print(f"Quy trình: {answer.process_id} | loại: {answer.kind} | model: {answer.model}")
    print(answer.prompt)
    return 0

  answer = assistant.ask(args.question, args.process, args.kind)
  print(f"Quy trình: {PROCESS_NAMES[answer.process_id]} | loại: {answer.kind} | model: {answer.model}")
  if answer.error:
    print(f"[LỖI] Không gọi được LLM ({settings.llm_base_url}): {answer.error}")
    return 1
  print(f"Trả lời: {answer.text}")
  if answer.verdict:
    print(f"Kết luận: {answer.verdict.upper()}")
  if answer.asked_node:
    print(f"Theo graph.json, sau '{answer.asked_node['name']}' là: "
          f"{[s['name'] for s in answer.expected_steps]} -> khớp: {answer.graph_agrees}")
  print("Nguồn:")
  for c in answer.citations:
    print(f"  #{c['rank']} {c['node_type']} {c['node_name'] or '(không tên)'} [{c['node_id']}] "
          f"score {c['score']}")
  return 0


if __name__ == "__main__":
  sys.stdout.reconfigure(encoding="utf-8", errors="replace")
  sys.exit(main())
