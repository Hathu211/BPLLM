import pandas as pd
import streamlit as st

from bpllm.config import get_settings
from bpllm.embeddings.embedder import ProcessEmbedder
from bpllm.llm.client import LLMClient
from bpllm.parsing import PROCESS_NAMES
from bpllm.rag.retriever import (Retriever, build_chat_messages, guess_process,
                                 process_profiles, split_answer)
from bpllm.vectorstore.qdrant_store import DEFAULT_TOP_K, QdrantVectorStore

# 1. Settings
settings = get_settings()

ALL_PROCESSES = "All Process Model"
# Tên hiển thị -> process_id lưu trong payload Qdrant (None = tự nhận diện quy trình).
# Tên phải trùng PROCESS_NAMES (tests/test_project_setup.py kiểm tra).
PROCESS_OPTIONS = {
    ALL_PROCESSES: None,
    "Food Delivery": "food_delivery",
    "E-commerce": "ecommerce",
    "Reimbursement": "reimbursement",
}
assert all(PROCESS_NAMES[pid] == name
           for name, pid in PROCESS_OPTIONS.items() if pid), "PROCESS_OPTIONS lệch PROCESS_NAMES"

UNAVAILABLE = "Sorry, the assistant is not available right now. Please try again later."

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
  embedder = ProcessEmbedder()
  vector_store = QdrantVectorStore()
  return embedder, vector_store, process_profiles(embedder)


try:
  embedder, vector_store, profiles = init_bpllm_components()
  retriever = Retriever(embedder, vector_store, top_k=DEFAULT_TOP_K)
  qdrant_ready = True
except Exception as e:
  qdrant_ready = False
  qdrant_error = str(e)

llm = LLMClient()


def resolve_process(question):
  """Quy trình đã chọn ở thanh bên; nếu chọn All thì nhận diện từ câu hỏi."""
  return process_id or guess_process(embedder.encode(question), profiles)


def results_table(results):
  return pd.DataFrame([
      {
          "Rank": f"#{rank}",
          "Cosine Score": f"{item['score']:.4f}",
          "Process": item["metadata"].get("process_name", "N/A"),
          "Node Type": item["metadata"].get("node_type", "N/A"),
          "Node Name": item["metadata"].get("node_name") or item["metadata"].get("node_id", ""),
          "Content Chunk (XML)": item["content"],
      }
      for rank, item in enumerate(results, 1)
  ])


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
    list(PROCESS_OPTIONS),
    index=1,  # mặc định Food Delivery: lọc theo quy trình cho kết quả tốt hơn
)
process_id = PROCESS_OPTIONS[selected_process]
if process_id is None:
  st.sidebar.info(
      "Tự nhận diện quy trình từ câu hỏi, sau đó chỉ tìm trong quy trình đó."
  )


# ==============================================================================
# VIEW 1: END-USER CHATBOT VIEW
# ==============================================================================
if view_mode == "End-User View":
  st.header("Business Process Conversational Assistant")
  st.caption("Ask a question and get a plain-language answer about the process.")

  if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role": "assistant",
        "content": "Hello! Ask me anything about how this process works.",
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
        response_text = UNAVAILABLE
      else:
        target = resolve_process(prompt)
        results = retriever.retrieve(prompt, process_id=target)
        if results:
          messages = build_chat_messages(prompt, results,
                                         st.session_state.messages[1:-1][-6:])
          try:
            with st.spinner("Thinking..."):
              _, response_text = split_answer(llm.chat(messages))
          except Exception:
            response_text = UNAVAILABLE
        else:
          response_text = "I could not find anything about that in this process."
        if process_id is None:
          st.caption(f"Process: {PROCESS_NAMES[target]}")

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
      "Admin panel to inspect retrieved chunks, cosine scores, the prompt sent"
      " to the LLM and its answer."
  )

  tab1, tab2, tab3 = st.tabs(
      ["LLM Answer Inspector", "Retrieval Inspector (Top-K Chunks)",
       "Vector DB Health & Stats"]
  )

  with tab1:
    st.subheader("LLM Answer Inspection")
    st.info(f"Active Process Filter: **{selected_process}** | Model: `{llm.model}`")

    inspect_query = st.text_input(
        "Enter a user question:",
        "What happens after the order is registered?",
        key="inspect_query",
    )

    if st.button("Run Full Pipeline"):
      if not qdrant_ready:
        st.error(f"gRPC Connection Failed: {qdrant_error}")
      else:
        target = resolve_process(inspect_query)
        chunks = retriever.retrieve(inspect_query, process_id=target)
        messages = build_chat_messages(inspect_query, chunks)
        st.write(f"Process used: **{PROCESS_NAMES[target]}**")

        try:
          with st.spinner("Generating answer..."):
            reasoning, answer = split_answer(llm.chat(messages))
          st.markdown("**Reasoning**")
          st.info(reasoning or "(model did not write a reasoning line)")
          st.markdown("**LLM answer**")
          st.success(answer)
        except Exception as error:
          st.error(f"LLM call failed: {error}")

        st.markdown("**Top-k chunks sent as context**")
        st.dataframe(results_table(chunks), use_container_width=True)
        with st.expander("Prompt sent to the LLM", expanded=True):
          for message in messages:
            st.code(f"[{message['role']}]\n{message['content']}", language="text")

  with tab2:
    st.subheader("Chunk Retrieval Inspection")
    st.info(f"Active Process Filter: **{selected_process}**")

    test_query = st.text_input(
        "Enter test query:",
        'Is there an activity with name="register the order"?',
    )
    top_k_val = st.slider("Select Top-K Chunks:", 1, 15, DEFAULT_TOP_K)

    if st.button("Run Vector Search Test") and qdrant_ready:
      retrieved_chunks = retriever.retrieve(test_query, process_id=process_id,
                                            top_k=top_k_val)
      st.success(
          f"Retrieved {len(retrieved_chunks)} chunks for filter"
          f" '{selected_process}'."
      )
      st.dataframe(results_table(retrieved_chunks), use_container_width=True)

  with tab3:
    st.subheader(
        "Qdrant Vector Store Infrastructure"
        f" (gRPC Port {settings.qdrant_grpc_port})"
    )
    if qdrant_ready:
      coll_info = vector_store.client.get_collection(
          vector_store.collection_name
      )

      col1, col2, col3, col4 = st.columns(4)
      col1.metric("Indexed Vectors", coll_info.points_count)
      col2.metric("Vector Dimension", coll_info.config.params.vectors.size)
      col3.metric(
          "Distance Metric", str(coll_info.config.params.vectors.distance)
      )
      col4.metric(
          "gRPC Connection", f"Connected ({settings.qdrant_grpc_port})"
      )
    else:
      st.error(f"gRPC Connection Failed: {qdrant_error}")