"""Giao diện BPLLM: hỏi đáp yes/no và "sau bước X là bước gì", có trích dẫn nguồn.

Chạy:  streamlit run app/streamlit_app.py
Cần: Qdrant đang bật, đã build vector store, server LLM trên Kaggle đang chạy và .env có LLM_BASE_URL.
"""
import pandas as pd
import streamlit as st

from bpllm.config import get_settings
from bpllm.embeddings.embedder import ProcessEmbedder
from bpllm.experiments import APP_MODEL_GROUP, MODEL_GROUPS, app_model
from bpllm.llm.client import LLMClient
from bpllm.parsing import PROCESS_NAMES
from bpllm.rag.assistant import Assistant, process_profiles
from bpllm.rag.question_type import NEXT_STEP, YESNO
from bpllm.rag.retriever import Retriever
from bpllm.vectorstore.qdrant_store import QdrantVectorStore

settings = get_settings()
COLLECTION = settings.collection(settings.app_chunking)

AUTO = "Tự nhận diện từ câu hỏi"
PROCESS_OPTIONS = {AUTO: None, **{name: pid for pid, name in PROCESS_NAMES.items()}}
KIND_OPTIONS = {"Tự nhận diện": None, "Yes / No": YESNO, "Bước tiếp theo": NEXT_STEP}
KIND_LABELS = {YESNO: "Yes / No", NEXT_STEP: "Bước tiếp theo"}
EXAMPLES = [
    "Is the rider paid at the end of the process?",
    "Does the customer have to create an account?",
    "What happens after the work proposal is sent?",
    "What do we do after reviewing the amount?",
    "Sau bước register new order thì là bước gì?",
]

st.set_page_config(page_title="BPLLM", page_icon="🤖", layout="wide")


@st.cache_resource(show_spinner="Đang nạp model embedding và kết nối Qdrant...")
def load_assistant():
  embedder = ProcessEmbedder()
  store = QdrantVectorStore(COLLECTION)
  if not store.exists():
    raise RuntimeError(f"Chưa có collection '{COLLECTION}'. Chạy scripts/build_vector_store.py.")
  return Assistant(embedder, Retriever(embedder, store, settings.top_k), LLMClient(),
                   process_profiles(embedder))


try:
  assistant = load_assistant()
  load_error = None
except Exception as error:
  assistant, load_error = None, f"{type(error).__name__}: {error}"

# ---------------- Thanh bên ----------------
st.sidebar.title("BPLLM")
view = st.sidebar.radio("Chế độ", ["Hỏi đáp", "Admin"])
process_label = st.sidebar.selectbox("Quy trình", list(PROCESS_OPTIONS))
process_id = PROCESS_OPTIONS[process_label]
kind_label = st.sidebar.selectbox("Loại câu hỏi", list(KIND_OPTIONS))
kind = KIND_OPTIONS[kind_label]
st.sidebar.caption(f"Chunk: **{settings.app_chunking}** (`{COLLECTION}`) · top-{settings.top_k}")
st.sidebar.caption(f"Model: bản **{settings.llm_quant}** · server `{settings.llm_base_url}`")
with st.sidebar.expander("Model dùng cho từng quy trình"):
  for pid, group in APP_MODEL_GROUP.items():
    st.write(f"**{PROCESS_NAMES[pid]}** → `{app_model(pid, settings.llm_quant)}`  \n"
             f"({MODEL_GROUPS[group].label})")

if load_error:
  st.error(f"Chưa sẵn sàng: {load_error}\n\n"
           "Kiểm tra: `docker compose -f docker_compose.yml up -d`, rồi "
           "`python scripts/build_vector_store.py`.")
  st.stop()


def show_citations(citations):
  st.markdown("**Nguồn (phần tử BPMN được dùng để trả lời)**")
  for c in citations:
    title = (f"#{c['rank']} · {c['node_type']} · {c['node_name'] or '(không tên)'} "
             f"[{c['node_id']}] · {PROCESS_NAMES.get(c['process_id'], c['process_id'])} · "
             f"score {c['score']}")
    with st.expander(title):
      st.code(c["text"], language="xml")


def show_answer(answer):
  st.caption(f"Quy trình: **{PROCESS_NAMES[answer.process_id]}** · "
             f"Loại: **{KIND_LABELS[answer.kind]}** · Model: `{answer.model}`")
  about = [answer.asked_node["name"]] if answer.asked_node else answer.names[:3]
  if about:
    st.caption("Hiểu câu hỏi nói về: " + ", ".join(f"**{n}**" for n in about))
  if answer.error:
    st.error("Không gọi được server LLM. Kiểm tra notebook Kaggle còn chạy và LLM_BASE_URL, "
             f"LLM_API_KEY trong .env.\n\n`{answer.error}`")
    return
  if answer.kind == YESNO:
    if answer.verdict == "yes":
      st.success("**YES**")
    elif answer.verdict == "no":
      st.error("**NO**")
    else:
      st.warning("Model không trả lời rõ yes/no.")
    st.write(answer.text)
  else:
    st.info(answer.text)
    if answer.asked_node is None:
      st.warning("Không nhận ra câu hỏi nói về bước nào nên chưa đối chiếu được với mô hình. "
                 "Thử nhắc vài từ trong tên bước, ví dụ: what happens after the payment is checked?")
    elif not answer.expected_steps:
      st.write(f"Theo mô hình, **{answer.asked_node['name']}** là bước cuối, không có bước sau.")
    else:
      expected = ", ".join(
          f"\"{s['name']}\"" + (f" (nếu {s['condition']})" if s["condition"] else "")
          for s in answer.expected_steps)
      icon = "✅" if answer.graph_agrees else "⚠️"
      st.write(f"{icon} Đối chiếu với mô hình BPMN: sau **{answer.asked_node['name']}** là {expected}.")
      if not answer.graph_agrees:
        st.caption("Câu trả lời của model chưa nhắc đủ các bước trên.")
  show_citations(answer.citations)


# ---------------- Hỏi đáp ----------------
if view == "Hỏi đáp":
  st.header("Hỏi đáp về quy trình")
  st.caption("Hỏi câu yes/no về quy trình, hoặc hỏi sau một bước thì đến bước nào, bằng lời "
             "của bạn; không cần viết đúng tên bước. Tên bước trong mô hình là tiếng Anh, nên hỏi "
             "tiếng Anh (hoặc giữ vài từ tiếng Anh của bước) sẽ nhận diện tốt nhất. "
             "Mỗi câu hỏi được trả lời độc lập.")
  with st.expander("Câu hỏi mẫu"):
    for example in EXAMPLES:
      st.code(example, language="text")
  question = st.chat_input("Nhập câu hỏi, ví dụ: What happens after the order is registered?")
  if question:
    with st.chat_message("user"):
      st.markdown(question)
    with st.chat_message("assistant"):
      with st.spinner("Đang truy xuất và hỏi model..."):
        answer = assistant.ask(question, process_id, kind)
      show_answer(answer)

# ---------------- Admin ----------------
else:
  st.header("Admin")
  question = st.text_input("Câu hỏi", EXAMPLES[2])
  call_llm = st.checkbox("Gọi LLM", value=True)
  if st.button("Chạy"):
    answer = assistant.ask(question, process_id, kind) if call_llm else \
        assistant.prepare(question, process_id, kind)
    if call_llm:
      show_answer(answer)
    else:
      st.caption(f"Quy trình: **{PROCESS_NAMES[answer.process_id]}** · "
                 f"Loại: **{KIND_LABELS[answer.kind]}** · Model: `{answer.model}`")
    st.subheader(f"Top-{len(answer.results)} chunk")
    st.dataframe(pd.DataFrame([{
        "rank": i, "score": round(r["score"], 4),
        "process": r["metadata"].get("process_id"), "type": r["metadata"].get("node_type"),
        "name": r["metadata"].get("node_name"), "id": r["metadata"].get("node_id")}
        for i, r in enumerate(answer.results, 1)]), use_container_width=True)
    with st.expander("Prompt gửi LLM", expanded=not call_llm):
      st.code(answer.prompt, language="text")
    if call_llm and answer.text:
      with st.expander("Nguyên văn câu trả lời"):
        st.code(answer.text, language="text")

  st.subheader("Trạng thái")
  st.write(f"Collection `{COLLECTION}`: {assistant.retriever.store.count()} chunk")
  if st.button("Kiểm tra server LLM"):
    try:
      served = assistant.llm.available_models()
      st.success(f"Server đang nạp: {served}")
    except Exception as error:
      st.error(f"Không gọi được {settings.llm_base_url}: {error}")
