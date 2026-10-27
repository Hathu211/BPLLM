import json
import os
import sys

# Append project base directory to sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from src.bpllm.embeddings.embedder import ProcessEmbedder
from src.bpllm.vectorstore.qdrant_store import QdrantVectorStore


def normalize_process_name(raw_name: str) -> str:
  """Standardize process names to match Streamlit UI selectbox options exactly."""
  name_lower = raw_name.lower()
  if "food" in name_lower or "delivery" in name_lower:
    return "Food Delivery"
  elif (
      "commerce" in name_lower
      or "e_commerce" in name_lower
      or "ecommerce" in name_lower
  ):
    return "E-commerce"
  elif "reimbursement" in name_lower:
    return "Reimbursement"
  return raw_name.replace("_", " ").title()


def load_all_process_chunks():
  """Load ground truth files and prepare chunks with standardized metadata."""
  gt_dir = os.path.join(BASE_DIR, "data", "ground_truth")
  chunks = []
  metadatas = []

  if not os.path.exists(gt_dir):
    print(f"Directory not found: {gt_dir}")
    return chunks, metadatas

  json_files = [f for f in os.listdir(gt_dir) if f.endswith(".json")]
  print(
      f" Found {len(json_files)} ground truth JSON file(s) in '{gt_dir}':"
      f" {json_files}"
  )

  for file_name in json_files:
    raw_proc_name = file_name.replace("_gt.json", "").replace(".json", "")
    proc_name = normalize_process_name(raw_proc_name)
    file_path = os.path.join(gt_dir, file_name)

    with open(file_path, "r", encoding="utf-8") as f:
      data = json.load(f)

    # 1. Activities Chunks
    for act in data.get("activities", []):
      chunk_text = f"Process: {proc_name} | Entity: Task/Activity | Name: {act}"
      chunks.append(chunk_text)
      metadatas.append({"process": proc_name, "type": "activity", "name": act})

    # 2. Gateways Chunks
    for gw in data.get("gateways", []):
      chunk_text = (
          f"Process: {proc_name} | Entity: Exclusive/Parallel Gateway | Name:"
          f" {gw}"
      )
      chunks.append(chunk_text)
      metadatas.append({"process": proc_name, "type": "gateway", "name": gw})

    # 3. Sequence Flows Chunks
    for flow in data.get("sequence_flows", []):
      src = flow.get("from", "")
      tgt = flow.get("to", "")
      chunk_text = (
          f"Process: {proc_name} | Sequence Flow: From '{src}' to '{tgt}'"
      )
      chunks.append(chunk_text)
      metadatas.append({
          "process": proc_name,
          "type": "sequence_flow",
          "from": src,
          "to": tgt,
      })

  return chunks, metadatas


def main():
  print("=" * 70)
  print(" STARTING VECTOR EMBEDDINGS INDEXING TO QDRANT VECTOR DB")
  print("=" * 70)

  # Step 1: Collect process chunks with normalized metadata
  chunks, metadatas = load_all_process_chunks()
  print(f"Total Process Chunks collected: {len(chunks)}")

  if not chunks:
    print(
        "No Chunks found to index! Check your 'data/ground_truth/'"
        " directory."
    )
    return

  # Step 2: Encode 384-dim vectors using all-MiniLM-L6-v2
  embedder = ProcessEmbedder(
      model_name="sentence-transformers/all-MiniLM-L6-v2"
  )
  embeddings = embedder.encode(chunks)

  # Step 3: Initialize Qdrant Store via gRPC Port 6334
  vector_store = QdrantVectorStore(
      host="localhost",
      grpc_port=6334,
      prefer_grpc=True,
      collection_name="bpllm_processes",
  )
  vector_store.init_collection(vector_size=384, recreate=True)

  # Step 4: Upsert vectors and metadata payloads into Qdrant
  vector_store.upsert_chunks(chunks, embeddings, metadatas)

  print("\n" + "=" * 70)
  print(" VECTOR STORE INDEXING COMPLETED SUCCESSFULLY!")
  print("=" * 70)


if __name__ == "__main__":
  main()