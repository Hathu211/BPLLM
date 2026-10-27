import os
import sys
import pandas as pd
import streamlit as st
from qdrant_client import QdrantClient

# 1. PYTHONPATH Setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from src.bpllm.embeddings.embedder import ProcessEmbedder
from src.bpllm.vectorstore.qdrant_store import QdrantVectorStore

# 2. Page Config
st.set_page_config(
    page_title="BPLLM Framework Dashboard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


# 3. Cache Components
@st.cache_resource
def init_bpllm_components():
  embedder = ProcessEmbedder("sentence-transformers/all-MiniLM-L6-v2")
  vector_store = QdrantVectorStore(
      host="localhost", grpc_port=6334, collection_name="bpllm_processes"
  )
  return embedder, vector_store


try:
  embedder, vector_store = init_bpllm_components()
  qdrant_ready = True
except Exception as e:
  qdrant_ready = False
  qdrant_error = str(e)


# 4. SIDEBAR
st.sidebar.title("BPLLM Framework")
st.sidebar.markdown("**Decision Support System for Business Processes**")
st.sidebar.divider()

view_mode = st.sidebar.radio(
    "Select View Mode:",
    ["End-User View", "Admin"],
)

st.sidebar.divider()
selected_process = st.sidebar.selectbox(
    "Select Business Process Filter:",
    ["All Process Model", "Food Delivery", "E-commerce", "Reimbursement"],
)


# ==============================================================================
# VIEW 1: END-USER CHATBOT VIEW
# ==============================================================================
if view_mode == "End-User View":
  st.header("Business Process Conversational Assistant")
  st.caption(
      "Conversational decision support assistant grounded in business process"
      " models."
  )

  if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role": "assistant",
        "content": (
            "Hello! I am the BPLLM assistant. Ask me about process structure or"
            " sequence flows."
        ),
    }]

  for message in st.session_state.messages:
    with st.chat_message(message["role"]):
      st.markdown(message["content"])

  if prompt := st.chat_input("Ask a question about the process..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
      st.markdown(prompt)

    with st.chat_message("assistant"):
      if not qdrant_ready:
        st.error(
            "❌ Cannot connect to Qdrant DB (Port 6334). Run 'docker-compose up"
            " -d'."
        )
      else:
        with st.spinner("Retrieving top chunks..."):
          query_vector = embedder.encode(prompt)

          # XỬ LÝ BỘ LỌC: Nếu chọn 'All Process Model' thì gán None để lấy tất cả chunks
          proc_filter = (
              None
              if selected_process == "All Process Model"
              else selected_process
          )

          results = vector_store.search_top_k(
              query_vector, top_k=10, process_filter=proc_filter
          )

        # Đã đưa về đúng khối lề thụt lề bên trong 'else'
        if results and len(results) > 0:
          top_score = results[0]["score"]
          top_chunk = results[0]["content"]
        else:
          top_score = 0.0
          top_chunk = "Not found"

        if top_score > 0.50:
          response_text = (
              f"**YES.** Statement verified against the"
              f" **{selected_process if selected_process != 'All Process Model' else 'selected'}**"
              " process model.\n\n"
              f"**Context Reference:**\n`{top_chunk}`\n\n"
              f"*(Similarity Score: {top_score:.4f})*"
          )
        else:
          response_text = (
              "**NO.** The queried element or sequence flow was not found in"
              " the process model."
          )

        st.markdown(response_text)
        st.session_state.messages.append(
            {"role": "assistant", "content": response_text}
        )


# ==============================================================================
# VIEW 2: ADMIN / RESEARCH VIEW
# ==============================================================================
else:
  st.header("Admin")
  st.caption(
      "Admin panel to inspect Vector Chunks, Cosine Similarity Scores, and"
      " Benchmark Metrics."
  )

  tab1, tab2 = st.tabs(
      ["Retrieval Inspector (Top-K Chunks)", "Vector DB Health & Stats"]
  )

  with tab1:
    st.subheader("Chunk Retrieval Inspection")
    st.info(f"Active Process Filter: **{selected_process}**")

    test_query = st.text_input(
        "Enter test query:",
        "Is there an activity with name='Register the order'?",
    )
    top_k_val = st.slider("Select Top-K Chunks:", 1, 15, 10)

    if st.button("Run Vector Search Test") and qdrant_ready:
      query_vec = embedder.encode(test_query)

      # XỬ LÝ BỘ LỌC ADMIN: Nếu chọn 'All Process Model' thì gán None
      proc_filter = (
          None if selected_process == "All Process Model" else selected_process
      )

      retrieved_chunks = vector_store.search_top_k(
          query_vec, top_k=top_k_val, process_filter=proc_filter
      )

      st.success(
          f"Successfully retrieved {len(retrieved_chunks)} Chunks for filter"
          f" '{selected_process}'!"
      )

      table_data = []
      for rank, item in enumerate(retrieved_chunks, 1):
        table_data.append({
            "Rank": f"#{rank}",
            "Cosine Score": f"{item['score']:.4f}",
            "Process": item["metadata"].get("process", "N/A"),
            "Entity Type": item["metadata"].get("type", "N/A"),
            "Content Chunk": item["content"],
        })

      st.dataframe(pd.DataFrame(table_data), use_container_width=True)

  with tab2:
    st.subheader("Qdrant Vector Store Infrastructure (gRPC Port 6334)")
    if qdrant_ready:
      client = QdrantClient(host="localhost", grpc_port=6334, prefer_grpc=True)
      coll_info = client.get_collection("bpllm_processes")

      col1, col2, col3, col4 = st.columns(4)
      col1.metric("Indexed Vectors", coll_info.points_count)
      col2.metric("Vector Dimension", coll_info.config.params.vectors.size)
      col3.metric(
          "Distance Metric", str(coll_info.config.params.vectors.distance)
      )
      col4.metric("gRPC Connection", "Connected (6334)")
    else:
      st.error(f"❌ gRPC Connection Failed: {qdrant_error}")