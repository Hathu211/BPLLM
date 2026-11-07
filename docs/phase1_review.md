# Phase 1 – Chuẩn hóa dữ liệu: những gì đã sửa và đánh giá

Ngày: 07/11/2026 · Đối chiếu với bài báo: Bernardi et al., *Conversing with business process-aware large language models: the BPLLM framework* (JIIS, 2024).

## 1. Tóm tắt nhanh

| | Trước khi sửa | Sau khi sửa |
| :--- | :--- | :--- |
| `python scripts/prepare_processes.py` | Lỗi `ImportError`, không chạy được | Chạy được, cả 3 quy trình đều OK |
| Output trong `data/processed/` | Cũ hơn code, xuống dòng kiểu Windows (CRLF), `graph.json` sai schema | Sinh lại từ code hiện tại, xuống dòng LF |
| `generate_ground_truth.py --check` | Không chạy được, vì phải chạy bước trên trước | OK cả 3 quy trình |
| Test Phase 1 (`test_parsing.py`, `test_phase1_pipeline.py`) | 85 pass, 22 lỗi | **111 pass, 0 lỗi** |

Nội dung ground truth (activity, gateway, flow) **không đổi**. Chỉ thêm một khóa mới là `dfg_activities`.

## 2. Các chỉnh sửa

### 2.1. Sửa lỗi import làm hỏng script chính
- **File:** `src/bpllm/parsing/__init__.py`
- **Lỗi:** `prepare_processes.py` gọi `clean_bpmn`, nhưng package chưa export hàm này. Vì vậy script dừng ngay từ dòng import.
- **Sửa:** export thêm `clean_bpmn`, `CleanResult` và `load_process`. `load_process` là hàm mà phase 2 sẽ dùng để đọc file BPMN người dùng upload.

### 2.2. Sửa 2 test lỗi thời
- **File:** `tests/test_phase1_pipeline.py`
- **Lỗi:** từ R8, `strip_bpmn_graphics.py` chỉ ghi vào `data/processed/_preview/`, nhưng test vẫn tìm file ở `data/processed/<pid>/`.
- **Sửa:** đổi đường dẫn trong `test_strip_script_handles_every_original` và `test_strip_script_continues_after_a_malformed_file`.

### 2.3. Thêm khóa `dfg_activities` vào ground truth
- **File:** `src/bpllm/parsing/ground_truth.py`, `data/ground_truth/*.json`
- **Lý do:** bài báo hiểu chữ "activity" bao gồm cả start event và end event. Trong bộ 104 câu hỏi, câu *"Is there an activity with name='customer order'?"* có đáp án **Yes**. Nhưng `activities` của mình chỉ chứa task. Phase sau nếu chỉ đọc `activities` sẽ chấm câu đó là No, tức là ngược với bài báo.
- **Sửa:** giữ nguyên `activities`, vẫn chỉ là task theo BPMN, để không làm hỏng code đang đọc khóa này. Thêm khóa `dfg_activities` gồm task, start event và end event. Khóa này đúng bằng danh sách trong `dfg_activities.txt` và trong file gốc của bài báo.
- **Quy ước từ giờ:** câu hỏi cấu trúc ("có activity X không?") đối chiếu với `dfg_activities`.

### 2.4. Nhánh XOR không có nhãn điều kiện được viết là "otherwise"
- **File:** `src/bpllm/parsing/dfg.py`
- **Lý do:** trong BPMN gốc của E-commerce, 2 nhánh không có nhãn. Natural text cũ ghi kiểu
  `From "Is this a new customer?", the process continues with "Recover client history".`,
  đọc lên như thể nhánh này luôn chạy, song song với nhánh "Yes".
- **Sửa:** nhánh không nhãn của gateway XOR/OR, khi các nhánh còn lại có nhãn, giờ được viết là
  `From "Is this a new customer?", the process can continue with "Recover client history" otherwise.`
  Ground truth giữ nguyên: không tự bịa nhãn "No".
- Food Delivery không có trường hợp này, nên `dfg_flows_paper.txt` của Food Delivery vẫn trùng với file của bài báo. Có test kiểm tra điều này.

### 2.5. Sửa 4 câu hỏi sai đáp án trong `data/questions/food_delivery_v1.json`
- **Lỗi:** câu 1, 5, 51 và 60 dùng tên không có trong BPMN, nhưng đáp án lại là Yes:
  - `'Customer Order Arrived'` (tên này lấy từ hình minh họa Fig. 5; tên thật là `customer order`)
  - `'Check CC and Payment'` (tên thật là `check credit card and the payment`)
- **Sửa:** thay bằng tên thật ở cả 8 câu có nhắc đến 2 tên này. Đáp án của cả 8 câu vẫn đúng sau khi thay.

### 2.6. Sinh lại toàn bộ output Phase 1
Đã chạy `prepare_processes.py`, rồi `generate_ground_truth.py`, rồi `generate_ground_truth.py --check`. Output giờ khớp với code:
- Xuống dòng LF (đúng R9).
- `graph.json` có `attached_to` và không còn `raw_name`.
- `phase1_report.json` có mục `renamed`.
- `dfg_flows_full.txt` dùng cách viết mới "(parallel branch)" / "(after all parallel branches complete)".

### 2.7. Test mới
- `test_unlabelled_xor_branch_is_written_as_otherwise`
- `test_food_delivery_text_has_no_otherwise_branch`
- `test_dfg_activities_follow_the_papers_definition`

## 3. Những điểm lệch với bài báo: giữ nguyên, nhưng cần nêu trong báo cáo

1. **Natural text bản `paper` thiếu 12/27 flow.** Đây là cách bài báo làm: bỏ mọi flow chạm vào gateway không tên. Code tái hiện đúng điều này. Chế độ `full` và `gateway` là **phần mở rộng của nhóm**, không có trong bài.
2. **Cleaner bỏ nhiều hơn "phần đồ họa".** Cleaner còn bỏ dataObject, ioSpecification, association, textAnnotation, documentation rỗng và một số thuộc tính của công cụ xuất. Nó cũng chuẩn hóa khoảng trắng trong tên và gán tên `payment database` / `customer database` cho data store, lấy từ annotation. Không ảnh hưởng 104 câu hỏi, nhưng chunk BPMN sẽ hơi khác chunk của bài.
3. **Thứ tự dòng trong file natural text sinh ra khác file gốc.** Nội dung thì giống. Với fixed/recursive chunking, thứ tự ảnh hưởng tới cách cắt chunk.

## 4. Đánh giá: dữ liệu đã đủ tốt cho các phase sau chưa?

**Kết luận: đã đủ dùng cho phase 2 và phase 3, với vài lưu ý về cách dùng ở bảng dưới.**

| Phase sau cần gì | Có sẵn chưa | Đánh giá |
| :--- | :--- | :--- |
| BPMN đã bỏ đồ họa để chunk theo thẻ BPMN (cấu hình tốt nhất của bài: Bảng 2, Fig. 3) | `data/processed/<pid>/<pid>.bpmn` | **Sẵn sàng.** Mỗi task/gateway/event còn đủ `<incoming>`/`<outgoing>` như Fig. 3. |
| Natural text (DFG) để so sánh RQ1–RQ3 | `dfg_activities.txt`, `dfg_flows_paper.txt` | **Sẵn sàng.** Với Food Delivery, nên dùng thẳng file gốc `data/raw/food_delivery_dfg_*.txt` để giữ đúng thứ tự dòng như bài (xem 3.3). |
| Ground truth để chấm accuracy (oracle) | `data/ground_truth/*.json` | **Sẵn sàng.** Trả lời đúng cả 104/104 câu của bài: activity dùng `dfg_activities`, flow dùng `sequence_flows`, loại gateway dùng `gateway_details`. |
| Nhiều quy trình cho RQ4 (Food + Reimbursement, Food + E-commerce) | Cả 3 quy trình đều hợp lệ | **Sẵn sàng.** Mỗi chunk đều có `process_name` thống nhất (Food Delivery / E-commerce / Reimbursement). Tên giống nhau giữa Food Delivery và E-commerce là đặc điểm có chủ ý của bài báo, không phải lỗi. |
| Bộ câu hỏi đánh giá | `3_questions_answers_refined.csv` (104 câu, 52 Yes / 52 No) | **Sẵn sàng.** Đây là benchmark chính. `food_delivery_v1.json` chỉ nên dùng cho demo: câu hỏi tiếng Việt đi với all-MiniLM-L6-v2 (chỉ hỗ trợ tiếng Anh) thì retrieval sẽ kém. |
| Đọc BPMN người dùng upload trên Streamlit | `load_process()` | **Sẵn sàng.** Hàm này làm sạch rồi parse, báo lỗi rõ khi file không phải BPMN 2.0. |

### Rủi ro ở phase sau (dữ liệu Phase 1 không sai, nhưng cách dùng cần xem lại)
- **Phase 2 – vector store:** `scripts/build_vector_store.py` đang tạo chunk từ ground truth JSON, kiểu `Process: … | Name: …`. Bài báo thì chunk **file BPMN theo thẻ XML**. Để tái hiện cấu hình tốt nhất, nên index `data/processed/<pid>/<pid>.bpmn` bằng chunking theo thẻ. Nếu vẫn giữ cách chunk từ JSON, thì nên dùng `dfg_activities` thay cho `activities`, để start/end event cũng có chunk riêng.
- **Phase 3 – fine-tune:** `scripts/prepare_dataset.py` lấy chính 104 câu benchmark làm dữ liệu train. Nếu đánh giá lại trên cùng 104 câu thì dữ liệu test đã lọt vào dữ liệu train, nên accuracy sẽ bị đẩy cao giả tạo. Nên sinh bộ train riêng từ `graph.json`, hoặc tách train/test.

## 5. Cách kiểm tra lại

```bash
python scripts/prepare_processes.py
python scripts/generate_ground_truth.py --check   # phải in [OK ] cho cả 3 quy trình
pytest tests/test_parsing.py tests/test_phase1_pipeline.py
```
