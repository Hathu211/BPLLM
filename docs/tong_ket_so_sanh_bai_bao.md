# Tổng kết dự án BPLLM và so sánh với bài báo

- **Ngày lập:** 16/11/2026
- **Nhánh:** `feat_hathu_setup_environment` (commit `a867535`)
- **Bài báo:** Bernardi, Casciani, Cimitile, Marrella. *Conversing with business process-aware large language models: the BPLLM framework*. Journal of Intelligent Information Systems 62 (2024). <https://link.springer.com/article/10.1007/s10844-024-00898-1>

Cách đọc cột "Đánh giá" trong các bảng:

| Nhãn | Nghĩa |
| :--- | :--- |
| **GIỐNG** | Làm đúng như bài báo mô tả |
| **KHÁC** | Làm theo cách khác, không nhằm tăng độ chính xác (lựa chọn kỹ thuật hoặc do điều kiện) |
| **CẢI TIẾN** | Phần dự án thêm vào, bài báo không có |
| **CHƯA LÀM** | Bài báo có, dự án chưa làm hoặc chưa có kết quả |

## 1. Kết quả chính

Cấu hình: BPMN, all-MiniLM-L6-v2, Qdrant cosine, top-10, Llama 3.1 8B đã fine-tune cho Food Delivery, 104 câu hỏi yes/no (52 yes, 52 no).

| Cấu hình | Accuracy | Đúng | Câu "yes" | Câu "no" |
| :--- | ---: | ---: | ---: | ---: |
| Bài báo, Bảng 4 (fine-tune, PEFT int4) | 92,31% | 96/104 | không nêu | không nêu |
| Dự án, chunk theo bài báo (`specific`) | 94,23% | 98/104 | 88,46% | 100% |
| Dự án, chunk cải tiến (`enriched`) | **100%** | 104/104 | 100% | 100% |

- Hai dòng của dự án lấy từ một lần chạy trên Kaggle ngày 12/11/2026 (2 GPU T4), bằng model của chính nhóm tác giả `angeloc1/llama3dot1FoodDel4v05`, trên bộ câu hỏi `6_questions_answers_refined_ft.csv`.
- Con số 96/104 của bài báo là tôi suy ra từ 92,31%; bài báo chỉ ghi phần trăm.
- Ba con số này **chưa so sánh ngang hàng tuyệt đối được**. Lý do nằm ở mục 6, cần đọc trước khi đưa vào báo cáo.

## 2. Bảng so sánh nhanh theo giai đoạn

| # | Giai đoạn | Bài báo | Dự án | Đánh giá |
| ---: | :--- | :--- | :--- | :--- |
| 1 | Chuẩn bị dữ liệu BPMN | Bỏ thông tin đồ họa khỏi BPMN | Pipeline 7 bước: làm sạch, parse thành graph, kiểm tra hợp lệ, đối chiếu | GIỐNG ở ý chính, CẢI TIẾN ở phần kiểm tra |
| 2 | Chunking | BPMN-specific: mỗi thẻ BPMN một chunk | Bản `specific` giống bài báo; thêm bản `enriched` | GIỐNG + CẢI TIẾN |
| 3 | Embedding | all-MiniLM-L6-v2 (384 chiều) | Cùng model | GIỐNG |
| 4 | Vector store | Qdrant, cosine, gRPC, qua LangChain | Qdrant, cosine, gRPC, gọi trực tiếp `qdrant-client` | GIỐNG về cấu hình, KHÁC về thư viện |
| 5 | Truy xuất | Top-10 chunk | Top-10 chunk, lọc theo quy trình | GIỐNG + CẢI TIẾN nhỏ |
| 6 | Prompt | Hình 4: câu lệnh, context, câu hỏi | Dùng đúng khuôn Hình 4 khi chạy model | GIỐNG |
| 7 | LLM và fine-tuning | Tự fine-tune Llama 3.1 8B bằng AutoTrain + PEFT (int4, int8) | Dùng lại model đã fine-tune của tác giả, không tự fine-tune | KHÁC, phần tự fine-tune CHƯA LÀM |
| 8 | Oracle | So câu trả lời với đáp án, tính accuracy | Cùng nguyên tắc, thêm accuracy theo lớp và danh sách câu sai | GIỐNG + CẢI TIẾN nhỏ |
| 9 | Các thí nghiệm so sánh (RQ1 đến RQ4) | 4 bảng kết quả | Chỉ có cấu hình tốt nhất của Bảng 4 | CHƯA LÀM phần lớn |

## 3. Chi tiết từng giai đoạn

### 3.1. Chuẩn bị dữ liệu (Phase 1)

File: `src/bpllm/parsing/`, `scripts/prepare_processes.py`. Kết quả: `data/processed/<quy_trình>/`.

| Bước | Bài báo | Dự án | Đánh giá |
| :--- | :--- | :--- | :--- |
| Quy trình sử dụng | Food Delivery, E-commerce, Reimbursement | Cùng 3 quy trình | GIỐNG |
| Bỏ đồ họa | Có, để vừa cửa sổ ngữ cảnh | Có (`BPMNDiagram`, `BPMNShape`, `BPMNEdge`...) | GIỐNG |
| Bỏ dữ liệu riêng của công cụ vẽ | Không nêu | Bỏ `BizagiExtensions`, `dataObject`, `textAnnotation`, `boundaryEvent` mồ côi, thuộc tính `exporter`, `gatewayDirection` | CẢI TIẾN |
| Chuẩn hóa tên | Không nêu | Gộp khoảng trắng thừa (1 trường hợp ở Food Delivery) | CẢI TIẾN |
| Kiểm tra hợp lệ | Không nêu | Flow phải trỏ tới node có thật, có start và end, mọi node đi tới được, không trùng tên | CẢI TIẾN |
| Nguồn dữ liệu chuẩn | Không nêu | `graph.json` cho mỗi quy trình; ground truth sinh từ đó | CẢI TIẾN |
| DFG dạng văn bản | Là một cách biểu diễn được đem ra thí nghiệm (Hình 5) | Có sinh file `dfg_*.txt` nhưng không đưa vào RAG | CHƯA LÀM phần thí nghiệm |

Số liệu: Food Delivery 17 activity, 6 gateway, 2 event, 27 flow; E-commerce 15, 4, 2, 22; Reimbursement 11, 5, 3, 20. Cả 3 quy trình 0 lỗi.

### 3.2. Chunking (Phase 2)

File: `src/bpllm/chunking/chunking_processor.py`.

| Điểm | Bài báo | Dự án | Đánh giá |
| :--- | :--- | :--- | :--- |
| Nguyên tắc | Cắt theo thẻ BPMN, mỗi phần tử là một chunk có nghĩa (Hình 3) | Mỗi node (task, gateway, event) là một chunk XML nguyên văn | GIỐNG |
| `<sequenceFlow>` | Không nêu rõ có thành chunk hay không | Không thành chunk riêng, vì chunk chỉ chứa id sẽ chiếm chỗ trong top-10 | KHÁC (lựa chọn của dự án) |
| Chunk `enriched` | Không có | Mỗi `<incoming>`/`<outgoing>` được gắn tên node ở đầu bên kia và nhãn điều kiện | **CẢI TIẾN chính** |
| Fixed-size, recursive | Có thí nghiệm (Bảng 2) | Không làm | CHƯA LÀM |
| Kiểm soát độ dài | Không nêu | Đo token: không chunk nào vượt 256 token của MiniLM | CẢI TIẾN |

Ví dụ cùng một node:

```xml
<!-- specific (theo bài báo) -->
<task id="Activity_074nbz9" name="register the order">
  <incoming>Flow_1tpgntx</incoming>
  <outgoing>Flow_0agx772</outgoing>
</task>

<!-- enriched (cải tiến) -->
<task id="Activity_074nbz9" name="register the order">
  <incoming source="Gateway_0z24z44">Flow_1tpgntx</incoming>
  <outgoing target="Gateway_1lf96zg">Flow_0agx772</outgoing>
</task>
```

Ở bản `specific`, muốn biết flow đi tới đâu model phải ghép id flow giữa hai chunk. Ở bản `enriched`, mỗi chunk tự nói được điều đó.

Kết quả: 65 chunk cho 3 quy trình (Food Delivery 25, E-commerce 21, Reimbursement 19). Độ dài trung bình 71 token (`specific`) và 93 token (`enriched`).

### 3.3. Embedding

File: `src/bpllm/embeddings/embedder.py`.

| Điểm | Bài báo | Dự án | Đánh giá |
| :--- | :--- | :--- | :--- |
| Model | all-MiniLM-L6-v2, 384 chiều (tốt nhất cho BPMN, Bảng 3) | Cùng model | GIỐNG |
| Chuẩn hóa vector | Không nêu | `normalize_embeddings=True` | KHÁC (chi tiết kỹ thuật, không đổi thứ hạng cosine) |
| So sánh model embedding khác | Có 2 model khác (Bảng 3) | Không làm | CHƯA LÀM |

### 3.4. Vector store

File: `src/bpllm/vectorstore/qdrant_store.py`, `docker_compose.yml`.

| Điểm | Bài báo | Dự án | Đánh giá |
| :--- | :--- | :--- | :--- |
| Cơ sở dữ liệu | Qdrant | Qdrant v1.10.1 chạy bằng Docker | GIỐNG |
| Khoảng cách | Cosine | Cosine | GIỐNG |
| Giao thức | gRPC | gRPC | GIỐNG |
| Thư viện | LangChain | Gọi trực tiếp `qdrant-client`, không qua LangChain | KHÁC |
| Id của điểm | Không nêu | UUID5 từ `process_id:node_id`, build lại không sinh điểm trùng | CẢI TIẾN |
| Payload index | Không nêu | Index trên `process_id` để lọc theo quy trình | CẢI TIẾN |
| Số collection | Một | Hai (`bpllm_processes`, `bpllm_processes_enriched`) để so sánh hai cách chunking | CẢI TIẾN |

### 3.5. Truy xuất top-10

File: `src/bpllm/rag/retriever.py`, `scripts/retrieve_top_k.py`.

| Điểm | Bài báo | Dự án | Đánh giá |
| :--- | :--- | :--- | :--- |
| Số chunk | 10 | 10 | GIỐNG |
| Phạm vi tìm | Kho chỉ chứa quy trình đang thí nghiệm | Kho chứa cả 3 quy trình, lọc theo `process_id` = Food Delivery | KHÁC về cách làm, cho kết quả tương đương kho một quy trình |
| Kiểm tra độ phủ | Chỉ nêu "top 10 luôn đủ" | Đo cụ thể: 52/52 câu "yes" có đủ node được hỏi trong top-10, ở cả hai bản | CẢI TIẾN |
| Làm sạch câu hỏi trước khi embed | Không có | Có tùy chọn `--clean-query` (mặc định tắt) | CẢI TIẾN (tùy chọn) |
| Đầu ra | Không nêu | File JSONL: câu hỏi, đáp án, 10 chunk kèm điểm, dùng lại được cho mọi model | CẢI TIẾN |

### 3.6. Prompt

| Điểm | Bài báo | Dự án | Đánh giá |
| :--- | :--- | :--- | :--- |
| Khuôn prompt khi chạy model | Hình 4: câu lệnh, các chunk, câu hỏi | Đúng khuôn đó, dựng từ trường `contexts` | GIỐNG |
| Câu hỏi | Bản "refined" trong gói replication | Dùng nguyên file 6 của gói replication | GIỐNG |
| Trường `input` trong JSONL | Không có | Có thêm dòng `Process: ...` và `Context BPMN:` | KHÁC, nhưng **không dùng** trong lần chạy có kết quả |

### 3.7. LLM và fine-tuning (Phase 3)

| Điểm | Bài báo | Dự án | Đánh giá |
| :--- | :--- | :--- | :--- |
| Model nền | Llama 3.1 8B Instruct | Cùng model nền | GIỐNG |
| Fine-tuning | Tự làm bằng AutoTrain Advanced + PEFT, lượng tử hóa int4 và int8 | Không tự fine-tune; tải model int4 đã fine-tune của tác giả từ Hugging Face | KHÁC |
| Phần cứng | NVIDIA A100 | Kaggle, 2 GPU T4 | KHÁC |
| Cách nạp model lúc suy luận | Không nêu | `float16`, không lượng tử hóa lúc nạp | KHÁC |
| Sinh câu trả lời | Không nêu tham số | Greedy (`do_sample=False`), tối đa 128 token, mỗi câu một hội thoại mới | KHÁC (chọn để kết quả lặp lại được) |
| Fine-tune riêng của nhóm | | Nhánh `feat_fine_tuning` có bộ dữ liệu 104 mẫu, nhưng tôi không thấy model hay kết quả nào từ bộ này | CHƯA LÀM |

Lưu ý về dữ liệu fine-tune trên nhánh `feat_fine_tuning`: 104 mẫu chính là 104 câu benchmark, context là JSON viết tay chứ không phải chunk XML, và 27 câu mở đầu bằng "Ignore your previous answers." đều gán nhãn "no". Nếu dùng bộ này để fine-tune rồi chấm trên chính 104 câu đó thì accuracy không có giá trị so sánh.

### 3.8. Oracle

File: `drafts/phase3/src/bpllm/evaluation/oracle.py` (bản nháp, chưa đưa vào `src/`), và khối oracle trong notebook Kaggle.

| Điểm | Bài báo | Dự án | Đánh giá |
| :--- | :--- | :--- | :--- |
| Nguyên tắc | So câu trả lời với đáp án nhị phân, accuracy = số đúng / tổng | Giống hệt | GIỐNG |
| Cách rút yes/no | Không nêu | Lấy từ `yes` hoặc `no` xuất hiện đầu tiên | KHÁC (bài báo không mô tả nên không đối chiếu được) |
| Accuracy riêng cho "yes" và "no" | Không có | Có | CẢI TIẾN |
| Câu không rút được yes/no | Không nêu | Tính là sai, liệt kê riêng | CẢI TIẾN |
| Danh sách câu sai kèm câu trả lời | Không có | Có, dùng để phân tích lỗi | CẢI TIẾN |

### 3.9. Phân tích 6 câu sai của bản `specific`

Cả 6 câu đều có đáp án "yes" và model trả lời "No". Bản `enriched` đúng cả 6.

| Câu | Nội dung | Model trả lời |
| ---: | :--- | :--- |
| 21 | Gateway có name="Gateway_0z24z44" là exclusive gateway? | Không có gateway nào mang *name* đó, chỉ có *id* đó |
| 24 | Gateway có name="Gateway_0yayjl1" là parallel gateway? | Tương tự: có id nhưng không có name |
| 25 | Gateway có name="Gateway_0iw6ax3" là parallel gateway? | "No", dù trích đúng chunk của gateway |
| 57 | Flow từ "check credit card and the payment" tới "Gateway_0z24z44"? | "No" |
| 58 | Flow từ "Gateway_0z24z44" tới "register the order"? | "No", dù tự nêu đúng id flow ở cả hai đầu |
| 77 | Flow từ "pay rider" tới "order completed"? (câu hỏi gốc thiếu một dấu ngoặc kép) | "No" |

Nhận xét:

- 5 trên 6 câu liên quan tới **gateway không có tên**, câu hỏi phải gọi chúng bằng id.
- Câu 57, 58, 77 hỏi về flow. Ở bản `specific`, model phải ghép id flow giữa hai chunk; ở bản `enriched`, tên node đích nằm ngay trong chunk. Đây là cách giải thích hợp lý nhất cho mức tăng, nhưng tôi chưa làm thí nghiệm tách riêng để khẳng định.
- Model không sai câu "no" nào ở cả hai bản: nó không bịa ra activity hay flow không tồn tại.

## 4. Phần bài báo có mà dự án chưa làm

| Thí nghiệm của bài báo | Kết quả bài báo | Dự án |
| :--- | :--- | :--- |
| RQ1: LLM thuần so với RAG (Bảng 1) | 42,78% so với 65,48% (văn bản) và 60,57% (BPMN), Llama 2 13B | Chưa làm |
| RQ2: fixed, recursive, không chunk; prompt refined và not refined (Bảng 2) | BPMN-specific + refined tốt nhất: 76,47% với Llama 2 13B | Chưa làm; chỉ dùng BPMN-specific + refined |
| RQ2: so sánh 7 LLM (Bảng 2) | Llama 3.1 8B Instruct tốt nhất: 90,38% | Chưa làm; chưa chạy cả Llama 3.1 8B chưa fine-tune |
| RQ3: văn bản DFG so với BPMN, 3 model embedding (Bảng 3) | BPMN + MiniLM: 90,38% | Chưa làm |
| RQ4: int4 so với int8 (Bảng 4) | 92,31% so với 90,58% | Chỉ chạy model int4 |
| RQ4: kho 2 quy trình (Bảng 4) | Food Delivery + Reimbursement: 84,62%; + E-commerce: 80,53% (int4) | Chưa chạy. Đã có sẵn file câu hỏi 4 (182 câu) và 5 (190 câu), và cả 3 quy trình đã nằm trong Qdrant |
| Đánh giá định tính (Hình 8) | Câu hỏi mở trên toàn bộ BPMN | Chưa làm |

Thiếu dòng "Llama 3.1 8B chưa fine-tune" nghĩa là dự án **chưa tự đo được fine-tuning đóng góp bao nhiêu**; hiện chỉ có thể dẫn con số 90,38% so với 92,31% của bài báo.

## 5. Danh sách cải tiến của dự án

Xếp theo mức ảnh hưởng tới kết quả:

1. **Chunk `enriched`**: gắn tên node nguồn, node đích và nhãn điều kiện vào `<incoming>`/`<outgoing>`. Từ 98/104 lên 104/104 trong lần chạy ngày 12/11. Đây là cải tiến duy nhất đã có số đo về accuracy.
2. **Pipeline chuẩn hóa dữ liệu có kiểm tra**: làm sạch, parse thành graph, kiểm tra hợp lệ, đối chiếu với bản mốc. `graph.json` khớp cả 104 nhãn của file câu hỏi 3.
3. **Lọc theo quy trình khi truy xuất**: cho phép giữ nhiều quy trình trong một kho mà không lẫn chunk. Chưa đo trên file 4 và 5.
4. **Oracle chi tiết hơn**: accuracy theo lớp, danh sách câu sai, câu không rút được yes/no.
5. **Đo độ phủ của bước truy xuất**: 52/52 câu "yes" có đủ node trong top-10, tách được lỗi truy xuất khỏi lỗi của model.
6. **Tính lặp lại**: id điểm ổn định, build lại sạch, 156 test tự động (chạy lại ngày 16/11/2026: 156 pass), file JSONL trung gian, giải mã greedy.
7. **Bộ câu hỏi mới (bộ 7)**: 104 câu diễn đạt khác, có 9 nhóm gồm cả câu bẫy (flow ngược chiều, flow cách hai bước, sai loại gateway). Đã có file top-10 nhưng tôi chưa thấy kết quả chạy model; xem mục 7.

## 6. Lưu ý khi viết báo cáo

1. **Không nên viết "vượt bài báo 7,69 điểm" mà không kèm điều kiện.** Bài báo không nói 92,31% đo trên file câu hỏi 3 hay 6, không mô tả cách rút yes/no, và pipeline của dự án khác ở vài điểm (không chunk `sequenceFlow`, có bước làm sạch, nạp model `float16`). Mức chênh giữa `specific` (94,23%) và bài báo (92,31%) chỉ là 2 câu.
2. **So sánh đáng tin nhất là `specific` so với `enriched`**, vì hai bản chạy cùng model, cùng câu hỏi, cùng prompt, chỉ khác chunk. Mức tăng 6 câu (5,77 điểm) là của riêng cải tiến chunking.
3. **Nguy cơ model đã thấy câu hỏi.** Model của tác giả được fine-tune cho Food Delivery và file 6 có đuôi `_ft`, nên nhiều khả năng các câu hỏi này nằm trong dữ liệu fine-tune. 100% trên bộ này chưa chứng minh model trả lời đúng với câu hỏi mới.
4. **Cỡ mẫu nhỏ, một lần chạy.** 104 câu, một quy trình, chạy một lần. Nên viết kèm số tuyệt đối (104/104, 98/104) thay vì chỉ phần trăm.
5. **Chunk `enriched` được thiết kế khi đã biết bộ benchmark này.** Kết quả trên bộ câu hỏi mới (bộ 7) hoặc trên E-commerce, Reimbursement mới cho biết cải tiến có tổng quát hay không.
6. **Model chưa từng được fine-tune trên chunk `enriched`** mà vẫn trả lời tốt hơn. Đây là điểm đáng nêu, nhưng nếu nhóm tự fine-tune thì dữ liệu fine-tune phải dùng đúng định dạng chunk lúc suy luận.
7. `docs/bao_cao_cong_viec.md` (11/11) ghi "chưa chạy LLM, chưa có oracle": phần đó đã cũ.

## 7. Việc còn lại nếu muốn hoàn thiện

| Việc | Vì sao |
| :--- | :--- |
| Chạy model trên bộ câu hỏi 7 (đã có `food_delivery_q7_top10*.jsonl`) | Có kết quả trên câu hỏi model chưa thấy, trả lời lưu ý 3 và 5 |
| Chạy Llama 3.1 8B Instruct chưa fine-tune trên cùng 2 file top-10 | Đo được đóng góp của fine-tuning, đối chiếu với 90,38% của bài báo |
| Chạy file câu hỏi 4 và 5 với kho nhiều quy trình | Tái lập nửa sau của Bảng 4 và kiểm tra lợi ích của việc lọc theo quy trình |
| Đưa `oracle.py` từ `drafts/phase3/` vào `src/bpllm/evaluation/` | Hiện `pytest drafts/phase3/tests` báo lỗi khi nạp test, nên oracle chưa được kiểm thử tự động trong repo |
| Lưu `answers_*.jsonl` và `accuracy_report.json` vào repo | Hiện kết quả chỉ nằm trong output của notebook |

## 8. Nguồn số liệu

| Số liệu | Nguồn |
| :--- | :--- |
| 94,23% và 100%, 6 câu sai | Output lưu trong notebook `food-delivery-model-template-chat.ipynb` (thư mục Downloads), chạy trên Kaggle ngày 12/11/2026. Notebook này chưa có trong repo |
| Đầu vào của lần chạy đó | `data/rag_inputs/food_delivery_ft_top10.jsonl`, `food_delivery_ft_top10_enriched.jsonl` (104 câu của file 6, lọc theo Food Delivery) |
| Số liệu Phase 1, chunking, truy xuất | `docs/bao_cao_cong_viec.md`, `data/processed/phase1_report.json` |
| Số liệu bài báo | Bảng 1 đến 4 và mục 4, 5 của bài báo, đọc ngày 16/11/2026 |
| 156 test pass | Chạy `pytest` ngày 16/11/2026 |
