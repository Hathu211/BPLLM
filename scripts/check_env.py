"""Kiểm tra môi trường: thư viện, cấu hình, Qdrant, model embedding, (tùy chọn) server LLM.

Chạy:  python scripts/check_env.py
       python scripts/check_env.py --llm     (kiểm tra thêm server LLM trên Kaggle)
"""
import argparse
import sys


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
  parser.add_argument("--llm", action="store_true", help="kiểm tra cả server LLM")
  args = parser.parse_args()
  ok = True

  try:
    import openai, qdrant_client, sentence_transformers, streamlit  # noqa: F401
    from bpllm.config import CHUNKINGS, get_settings
    settings = get_settings()
    print("[OK ] 1. Thư viện và cấu hình")
  except Exception as e:
    print(f"[LỖI] 1. Thư viện / cấu hình: {e}\n      Chạy: pip install -e \".[dev]\" và kiểm tra .env")
    return 1

  try:
    from bpllm.vectorstore.qdrant_store import QdrantVectorStore
    for chunking in CHUNKINGS:
      store = QdrantVectorStore(settings.collection(chunking))
      if store.exists():
        print(f"[OK ] 2. Qdrant: {store.collection_name} có {store.count()} chunk '{store.chunking()}'")
      else:
        print(f"[ -- ] 2. Qdrant: chưa có collection {store.collection_name} "
              "(chạy scripts/build_vector_store.py)")
  except Exception as e:
    ok = False
    print(f"[LỖI] 2. Không kết nối được Qdrant {settings.qdrant_host}:{settings.qdrant_grpc_port}: {e}\n"
          "      Bật Docker Desktop rồi chạy: docker compose -f docker_compose.yml up -d")

  try:
    from bpllm.embeddings.embedder import ProcessEmbedder
    print(f"[OK ] 3. Embedding {settings.embedding_model}: "
          f"{len(ProcessEmbedder().encode('test BPMN chunk'))} chiều")
  except Exception as e:
    ok = False
    print(f"[LỖI] 3. Model embedding: {e}")

  if args.llm:
    try:
      from bpllm.experiments import APP_MODEL_GROUP, app_model
      from bpllm.llm.client import LLMClient
      served = LLMClient().available_models()
      print(f"[OK ] 4. Server LLM {settings.llm_base_url}: {served}")
      for pid in APP_MODEL_GROUP:
        model = app_model(pid, settings.llm_quant)
        if model not in served:
          ok = False
          print(f"[LỖI]    thiếu model {model} cho quy trình {pid}")
    except Exception as e:
      ok = False
      print(f"[LỖI] 4. Không gọi được server LLM {settings.llm_base_url}: {e}")
      from bpllm.config import PROJECT_ROOT
      env_file = PROJECT_ROOT / ".env"
      if "localhost" in settings.llm_base_url or "127.0.0.1" in settings.llm_base_url:
        print(f"      LLM_BASE_URL vẫn trỏ về máy này. Sửa {env_file}: dán link Khối 6 của notebook "
              "server Kaggle, dạng https://....trycloudflare.com/v1 (hoặc ....ngrok-free.app/v1).")
      elif not settings.llm_base_url.rstrip("/").endswith("/v1"):
        print("      LLM_BASE_URL phải kết thúc bằng /v1.")
      else:
        print("      Kiểm tra notebook server Kaggle còn chạy (Khối 7 in 'tunnel ... OK'); "
              "mỗi lần chạy lại Khối 6, link đổi và phải sửa lại .env.")
      if settings.llm_api_key == "change-me":
        print(f"      LLM_API_KEY vẫn là 'change-me': đặt bằng giá trị secret BPLLM_API_KEY trên Kaggle.")

  print("SẴN SÀNG" if ok else "CÓ LỖI, xem các dòng [LỖI] ở trên")
  return 0 if ok else 1


if __name__ == "__main__":
  sys.stdout.reconfigure(encoding="utf-8", errors="replace")
  sys.exit(main())
