# BPLLM 2

Trợ lý hỏi đáp về quy trình nghiệp vụ, trả lời dựa trên mô hình BPMN. Tái lập framework BPLLM
(Bernardi, Casciani, Cimitile, Marrella, *Conversing with business process-aware large language
models: the BPLLM framework*, JIIS 2024) với cấu hình tốt nhất của bài báo, cộng thêm phần mở rộng
**chunk enriched**.

```
BPMN gốc ─► làm sạch ─► graph.json ─► chunk (specific | enriched) ─► MiniLM ─► Qdrant
                                                                              │ top-10
câu hỏi ─────────────────────────────────────────────────────────────────────►┤
                                                                              ▼
              Llama 3.1 8B fine-tune của tác giả (Kaggle) ◄── prompt Hình 4 ◄─┘
                       │
                       ├─► oracle (yes/no, accuracy)         notebook thực nghiệm
                       └─► Streamlit (yes/no, bước tiếp theo, trích dẫn nguồn)
```

**Hướng dẫn chạy từ đầu đến cuối: [docs/huong_dan_chay.md](docs/huong_dan_chay.md).**
So sánh với bài báo: [docs/so_sanh_bai_bao.md](docs/so_sanh_bai_bao.md).

## Chạy nhanh (PowerShell, ở thư mục `C:\BPLLM`)

```powershell
py -3.11 -m venv venv_bpllm2
venv_bpllm2\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
docker compose -f docker_compose.yml up -d
python scripts/prepare_processes.py
python scripts/generate_ground_truth.py
python scripts/build_vector_store.py
python scripts/retrieve_top_k.py
pytest
streamlit run app/streamlit_app.py
```

Phần chạy LLM nằm trên Kaggle (GPU miễn phí): `notebooks/bpllm_experiment_kaggle.ipynb` cho thực
nghiệm, `notebooks/bpllm_server_kaggle.ipynb` làm server cho Streamlit.

## 6 model của bài báo

| Nhóm | Quy trình | int4 | int8 |
| :--- | :--- | :--- | :--- |
| `food_delivery` | Food Delivery | `angeloc1/llama3dot1FoodDel4v05` | `angeloc1/llama3dot1FoodDel8v02` |
| `similar` | Food Delivery + E-commerce | `angeloc1/llama3dot1SimilarProcesses4` | `angeloc1/llama3dot1SimilarProcesses8` |
| `different` | Food Delivery + Reimbursement | `angeloc1/llama3dot1DifferentProcesses4` | `angeloc1/llama3dot1DifferentProcesses8` |

Cả 6 là model Llama 3.1 8B Instruct đã merge, trọng số F16 (16,1 GB). "int4/int8" là cách tác
giả fine-tune (PEFT), không phải định dạng trọng số. Streamlit gọi model theo quy trình:
Food Delivery → `food_delivery`, E-commerce → `similar`, Reimbursement → `different`.

## Cấu trúc thư mục

| Đường dẫn | Nội dung |
| :--- | :--- |
| `src/bpllm/config.py` | Nơi duy nhất đọc cấu hình (`.env`) |
| `src/bpllm/experiments.py` | 6 model, 4 thực nghiệm, tên file input/output |
| `src/bpllm/parsing/` | Làm sạch BPMN, parse thành graph, sinh DFG text, ground truth |
| `src/bpllm/chunking/` | Chunk `specific` (Hình 3 bài báo) và `enriched` (mở rộng) |
| `src/bpllm/embeddings/`, `vectorstore/` | MiniLM, Qdrant (cosine, gRPC, lọc theo quy trình) |
| `src/bpllm/rag/` | Prompt, truy xuất, loại câu hỏi, tra graph, trích dẫn, luồng trả lời |
| `src/bpllm/llm/` | Client gọi server chuẩn OpenAI trên Kaggle |
| `src/bpllm/evaluation/` | Oracle yes/no |
| `scripts/` | Các bước của pipeline, xem hướng dẫn chạy |
| `app/` | Streamlit |
| `notebooks/` | 2 notebook Kaggle |
| `data/raw/original/` | BPMN gốc (đầu vào) |
| `data/raw/` | BPMN đã làm sạch dùng làm mốc đối chiếu, DFG text của bài báo |
| `data/questions/` | Bộ câu hỏi 3, 4, 5, 6 của bài báo |
| `data/processed/`, `data/ground_truth/` | Sinh tự động ở Phase 1, không sửa tay |
| `data/rag_inputs/` | File top-10 cho notebook thực nghiệm (sinh ở Phase 4) |
| `data/results/` | Câu trả lời tải về từ Kaggle và bảng tổng hợp |
| `tests/` | pytest, không cần Docker hay mạng |
