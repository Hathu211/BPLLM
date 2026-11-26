# BPLLM 2 so với bài báo

Bài báo: Bernardi, Casciani, Cimitile, Marrella. *Conversing with business process-aware large
language models: the BPLLM framework*. JIIS 62 (2024).
<https://link.springer.com/article/10.1007/s10844-024-00898-1>

Phạm vi: dựng BPLLM hoàn chỉnh với cấu hình tốt nhất của bài báo và tái lập Bảng 4 (model
fine-tune). Không tái lập RQ1 đến RQ3 (LLM không RAG, các kiểu chunk khác, văn bản DFG, các
model embedding và LLM khác).

| Nhãn | Nghĩa |
| :--- | :--- |
| **GIỐNG** | Làm như bài báo mô tả |
| **KHÁC** | Làm khác, do điều kiện hoặc lựa chọn kỹ thuật |
| **MỞ RỘNG** | Bài báo không có |

## Từng giai đoạn

| Giai đoạn | Bài báo | BPLLM 2 | Đánh giá |
| :--- | :--- | :--- | :--- |
| Dữ liệu | 3 quy trình BPMN, bỏ thông tin đồ họa | Cùng 3 quy trình; bỏ đồ họa và phần riêng của công cụ vẽ; parse thành graph, kiểm tra hợp lệ, đối chiếu với bản mốc | GIỐNG, MỞ RỘNG ở phần kiểm tra |
| Chunking | BPMN-specific, mỗi thẻ BPMN một chunk (Hình 3) | `specific`: mỗi task/gateway/event một chunk, nguyên văn XML. Không tạo chunk riêng cho `<sequenceFlow>` vì flow đã đọc được qua id trong `<incoming>`/`<outgoing>` | GIỐNG ở ý chính, KHÁC ở `sequenceFlow` |
| Chunk enriched | Không có | `<incoming source=...>`, `<outgoing target=... condition=...>` | MỞ RỘNG |
| Embedding | all-MiniLM-L6-v2 | Cùng model | GIỐNG |
| Vector store | Qdrant, cosine, gRPC, qua LangChain | Qdrant, cosine, gRPC, gọi trực tiếp `qdrant-client` | GIỐNG cấu hình, KHÁC thư viện |
| Truy xuất | Top-10 | Top-10; kho của mỗi thực nghiệm gồm đúng các quy trình của nhóm model | GIỐNG |
| Prompt | Hình 4: câu lệnh, context, câu hỏi | Cùng khuôn, gửi qua chat template Llama 3.1; một khuôn duy nhất cho thực nghiệm và app (`src/bpllm/rag/prompts.py`) | GIỐNG |
| LLM | Llama 3.1 8B fine-tune bằng AutoTrain + PEFT int4/int8 | Dùng lại 6 model của tác giả trên Hugging Face, không tự fine-tune | GIỐNG model, KHÁC ở chỗ không tự train |
| Phần cứng | NVIDIA A100 | Kaggle, 2 × T4, F16, giải mã greedy | KHÁC |
| Oracle | So yes/no với đáp án, accuracy | Cùng nguyên tắc; thêm accuracy theo lớp, câu sai, câu không rút được yes/no | GIỐNG, MỞ RỘNG nhỏ |
| Giao diện | Trợ lý hội thoại | Streamlit: yes/no và "bước tiếp theo", trích dẫn phần tử BPMN, đối chiếu với graph; Admin xem top-k và prompt | MỞ RỘNG |

## Thực nghiệm tái lập (Bảng 4)

| Thực nghiệm | Bộ câu hỏi | Kho | Model |
| :--- | :--- | :--- | :--- |
| `fd_refined`, `fd_ft` | 3, 6 (104 câu) | Food Delivery | FoodDel4v05, FoodDel8v02 |
| `similar` | 5 (190 câu) | Food Delivery + E-commerce | SimilarProcesses4, SimilarProcesses8 |
| `different` | 4 (182 câu) | Food Delivery + Reimbursement | DifferentProcesses4, DifferentProcesses8 |

Mỗi thực nghiệm chạy cả `specific` và `enriched`. Kết quả nằm ở `data/results/summary.md` sau
khi chạy `python scripts/evaluate.py`; đối chiếu với Bảng 4 trong bài báo.

Mốc của bài báo cho bản int4 (Bảng 4, ghi lại từ model card trên Hugging Face ngày 12/11/2026;
bản int8 xem trực tiếp Bảng 4):

| Model | Bộ câu hỏi | Accuracy bài báo |
| :--- | :--- | ---: |
| FoodDel4v05 | 104 câu Food Delivery (bài báo không nói file 3 hay 6) | 92,31% |
| SimilarProcesses4 | 5 (190 câu) | 80,53% (153/190) |
| DifferentProcesses4 | 4 (182 câu) | 84,62% (154/182) |

Lần chạy trên repo cũ (Kaggle, 12/11/2026, FoodDel4v05, F16, bộ 6) cho `specific` 98/104 = 94,23%
và `enriched` 104/104. File input `fd_ft_specific_top10.jsonl` của BPLLM 2 cho cùng top-10 và cùng
điểm cosine với input của lần chạy đó.

## Lưu ý khi so sánh

1. Hai model 8B của cùng nhóm có tên int4/int8, nhưng trọng số đều F16; khác nhau ở cách fine-tune.
2. Bộ câu hỏi 6 có đuôi `_ft`, nhiều khả năng đã nằm trong dữ liệu fine-tune của tác giả. Kết quả
   cao trên bộ này chưa chứng minh model trả lời tốt câu hỏi mới.
3. So sánh đáng tin nhất là `specific` với `enriched` trên cùng model và cùng câu hỏi.
4. Server cho Streamlit nén model 4-bit để vừa GPU miễn phí, nên câu trả lời trên app có thể khác
   một chút so với notebook thực nghiệm (F16). Số liệu chỉ lấy từ notebook thực nghiệm.
5. Câu "bước tiếp theo" không có trong dữ liệu fine-tune của tác giả; app đối chiếu câu trả lời
   với `graph.json` và cảnh báo khi thiếu bước.
