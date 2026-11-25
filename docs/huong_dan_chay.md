# Hướng dẫn chạy BPLLM 2 từ đầu

Mọi lệnh chạy trong **PowerShell**, ở thư mục `C:\BPLLM`, sau khi đã kích hoạt môi trường ảo
(bước 0.3). Mỗi bước có phần **Kiểm tra** để biết đã chạy đúng.

Tổng quan:

| Bước | Ở đâu | Làm gì |
| :--- | :--- | :--- |
| 0 | Máy bạn | Môi trường, Docker, `.env` |
| 1 | Máy bạn | Chuẩn hóa BPMN, sinh graph và ground truth |
| 2 + 3 | Máy bạn | Chunk và nạp 2 collection Qdrant |
| 4 | Máy bạn | Sinh file top-10 cho thực nghiệm |
| 5 | Kaggle | Chạy 6 model, chấm oracle |
| 6 | Máy bạn | Tổng hợp kết quả |
| 7 | Kaggle + máy bạn | Server LLM + Streamlit |

---

## Bước 0. Môi trường

**Cần có:** Python 3.11 (`py -3.11 --version`), Docker Desktop đang chạy, tài khoản Kaggle đã
xác minh số điện thoại (để bật GPU và Internet).

**0.1. Tạo môi trường ảo**

```powershell
cd C:\BPLLM
py -3.11 -m venv venv_bpllm2
```

**0.2. Nếu PowerShell chặn script kích hoạt** (chỉ cần một lần):

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

**0.3. Kích hoạt và cài đặt** (lần đầu tải torch khoảng 200 MB đến 2 GB)

```powershell
venv_bpllm2\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

**0.4. Tạo `.env`**

```powershell
Copy-Item .env.example .env
```

Chưa cần sửa gì; `LLM_BASE_URL` và `LLM_API_KEY` sẽ điền ở Bước 7.

**0.5. Bật Qdrant** (container `bpllm2-qdrant`, cổng 6343/6344, không đụng tới repo cũ)

```powershell
docker compose -f docker_compose.yml up -d
```

**Kiểm tra:** `docker ps` có dòng `bpllm2-qdrant`; mở <http://localhost:6343/dashboard>.

```powershell
python scripts/check_env.py
```

Lúc này dòng 2 báo "chưa có collection" là bình thường.

---

## Bước 1. Chuẩn hóa quy trình (Phase 1)

```powershell
python scripts/prepare_processes.py
python scripts/generate_ground_truth.py
```

- `prepare_processes.py`: đọc `data/raw/original/*.bpmn`, bỏ phần đồ họa và phần riêng của công
  cụ vẽ, kiểm tra graph hợp lệ, đối chiếu với `data/raw/*.bpmn`, ghi `data/processed/<quy trình>/`.
- `generate_ground_truth.py`: sinh `data/ground_truth/<quy trình>.json` từ graph.

**Kiểm tra:** cả hai lệnh in `[OK ]` cho 3 quy trình: food_delivery (17 activity, 27 flow),
ecommerce (15, 22), reimbursement (11, 20).

---

## Bước 2 + 3. Chunk và nạp Qdrant

```powershell
python scripts/build_vector_store.py
```

Tạo lại **2 collection**, mỗi collection chứa cả 3 quy trình:

| Collection | Chunk | Dùng cho |
| :--- | :--- | :--- |
| `bpllm2_specific` | Nguyên văn XML mỗi phần tử BPMN (Hình 3 bài báo) | Thực nghiệm, so sánh |
| `bpllm2_enriched` | Như trên, `<incoming>`/`<outgoing>` có thêm tên bước nguồn/đích và nhãn nhánh | Thực nghiệm và Streamlit |

Tên collection suy ra từ kiểu chunk, nên không thể nạp nhầm.

**Kiểm tra:** in `[OK ] bpllm2_specific: 65 chunk ...` và `[OK ] bpllm2_enriched: 65 chunk ...`
(25 Food Delivery, 21 E-commerce, 19 Reimbursement). `python scripts/check_env.py` báo cả hai collection.

---

## Bước 4. Sinh file top-10 cho thực nghiệm

```powershell
python scripts/retrieve_top_k.py
```

Ghi 8 file vào `data/rag_inputs/` (4 thực nghiệm × 2 kiểu chunk):

| Thực nghiệm | Bộ câu hỏi | Kho truy xuất | Nhóm model | File |
| :--- | :--- | :--- | :--- | :--- |
| `fd_refined` | 3 (104 câu) | Food Delivery | food_delivery | `fd_refined_{specific,enriched}_top10.jsonl` |
| `fd_ft` | 6 (104 câu) | Food Delivery | food_delivery | `fd_ft_{specific,enriched}_top10.jsonl` |
| `similar` | 5 (190 câu) | Food Delivery + E-commerce | similar | `similar_{specific,enriched}_top10.jsonl` |
| `different` | 4 (182 câu) | Food Delivery + Reimbursement | different | `different_{specific,enriched}_top10.jsonl` |

Mỗi dòng có trường `prompt` dựng sẵn (khuôn Hình 4); notebook gửi nguyên văn trường này.
Script kiểm tra collection chứa đúng loại chunk trước khi chạy, nên file `specific` không thể bị
lẫn chunk `enriched`.

**Kiểm tra:** 8 dòng `[OK ]`.

---

## Bước 5. Chạy thực nghiệm trên Kaggle

**5.1. Tạo dataset chứa input**

1. Vào <https://www.kaggle.com/datasets> → **New Dataset**.
2. Kéo thả 8 file trong `C:\BPLLM\data\rag_inputs\` (các file `*_top10.jsonl`).
3. Đặt tên, ví dụ `bpllm2-rag-inputs`, chọn Private, bấm **Create**.

Khi sinh lại file ở Bước 4, vào dataset → **New Version** để cập nhật.

**5.2. Mở notebook**

1. <https://www.kaggle.com/code> → **New Notebook** → **File → Import Notebook** → chọn
   `C:\BPLLM\notebooks\bpllm_experiment_kaggle.ipynb`.
2. Cột bên phải: **Session options → Accelerator: GPU T4 x2**, **Internet: On**.
3. **Add Input** → tab **Your Work / Datasets** → chọn `bpllm2-rag-inputs`.

**5.3. Chạy**

Ở Khối 1 đặt `EXPERIMENT` và `QUANT`, rồi **Run All**. Mỗi model tải khoảng 16 GB (5 đến 10
phút). 104 câu × 2 kiểu chunk mất khoảng 15 đến 30 phút trên 2 T4.

Thứ tự đề xuất (8 lần chạy, đổi Khối 1 rồi chạy lại từ Khối 1):

| Lần | `EXPERIMENT` | `QUANT` | Model |
| ---: | :--- | :--- | :--- |
| 1 | `fd_ft` | `int4` | FoodDel4v05 |
| 2 | `fd_refined` | `int4` | FoodDel4v05 (không tải lại) |
| 3 | `fd_ft` | `int8` | FoodDel8v02 |
| 4 | `fd_refined` | `int8` | FoodDel8v02 |
| 5 | `similar` | `int4` | SimilarProcesses4 |
| 6 | `similar` | `int8` | SimilarProcesses8 |
| 7 | `different` | `int4` | DifferentProcesses4 |
| 8 | `different` | `int8` | DifferentProcesses8 |

Phiên bị ngắt giữa chừng: chạy lại Khối 1 đến 6 rồi Khối 8; câu đã làm được bỏ qua.

Nên thêm **Add-ons → Secrets → `HF_TOKEN`** (token đọc tạo ở
<https://huggingface.co/settings/tokens>) để Hugging Face không giới hạn tốc độ tải ẩn danh.

**Kiểm tra:** Khối 7 in prompt và câu trả lời có `yes`/`no`; Khối 10 in accuracy của từng kiểu chunk.

**5.4. Tải kết quả**

Cột bên phải → **Output** (`/kaggle/working`) → tải các file `answers_*.jsonl` (và
`report_*.json` nếu muốn) về `C:\BPLLM\data\results\`. Output mất khi phiên tắt, nên tải ngay
sau mỗi lần chạy.

---

## Bước 6. Tổng hợp kết quả

```powershell
python scripts/evaluate.py
```

In bảng accuracy cho mọi file trong `data/results/` và ghi `data/results/summary.md`,
`summary.json`. Chấm lại một file:

```powershell
python -m bpllm.evaluation.oracle data/results/answers_fd_ft_enriched_int4.jsonl
```

---

## Bước 7. Streamlit với model fine-tune

**7.1. Bật server LLM trên Kaggle**

1. Tạo **notebook mới** (không dùng chung với notebook thực nghiệm), import
   `C:\BPLLM\notebooks\bpllm_server_kaggle.ipynb`.
2. Accelerator **GPU T4 x2**, Internet **On**.
3. **Add-ons → Secrets → Add a new secret**: Label `BPLLM_API_KEY`, Value là một chuỗi bí mật bạn
   tự đặt (ví dụ 32 ký tự ngẫu nhiên). Thêm secret thứ hai `HF_TOKEN` (token đọc tạo ở
   <https://huggingface.co/settings/tokens>), không bắt buộc nhưng tránh bị giới hạn khi tải 3 × 16 GB.
   Bật công tắc gắn cả hai secret vào notebook.
4. **Run All**. Khối 3b tải và nạp lần lượt 3 model bản int4 (nén 4-bit để vừa 2 GPU), mất khoảng
   15 đến 25 phút. Khối 3a in dung lượng ổ trống; Khối 2 in phiên bản thư viện.
5. Khối 6 mở link công khai, gọi thử `/v1/models` qua link đó, rồi mới in
   `LLM_BASE_URL=https://....trycloudflare.com/v1`. Nếu Cloudflare không cấp được link (Kaggle
   chặn hoặc bị giới hạn), khối báo lỗi kèm log. Khi đó:
   - tạo tài khoản ngrok miễn phí, lấy authtoken ở <https://dashboard.ngrok.com/get-started/your-authtoken>;
   - thêm Kaggle Secret `NGROK_AUTHTOKEN`, bật công tắc gắn vào notebook;
   - chạy lại **chỉ Khối 6**; link sẽ có dạng `https://....ngrok-free.app/v1`.
6. Giữ tab notebook mở; Khối 7 chạy liên tục để giữ phiên.

**7.2. Trỏ app tới server.** Sửa `C:\BPLLM\.env`:

```
LLM_BASE_URL=https://....trycloudflare.com/v1
LLM_API_KEY=<giá trị BPLLM_API_KEY>
```

**Kiểm tra:**

```powershell
python scripts/check_env.py --llm
python scripts/ask.py "What happens after \"send work proposal\"?" --process food_delivery
```

Dòng 4 của `check_env` liệt kê 3 model; `ask.py` in câu trả lời, phần đối chiếu graph và nguồn.

**7.3. Mở giao diện**

```powershell
streamlit run app/streamlit_app.py
```

Trình duyệt mở <http://localhost:8501>.

- **Hỏi đáp:** chọn quy trình (hoặc để tự nhận diện) và loại câu hỏi (hoặc để tự nhận diện).
  - Câu yes/no, ví dụ `Is the rider paid at the end of the process?` → hiện **YES/NO**, câu trả lời
    của model và các phần tử BPMN làm nguồn (mở ra xem XML).
  - Câu bước tiếp theo, ví dụ `What happens after the work proposal is sent?` hoặc
    `Sau bước register new order thì là bước gì?` → câu trả lời của model, kèm ✅/⚠️ đối chiếu
    với `graph.json` và nguồn.
  - Không cần ngoặc kép hay đúng tên bước: app nhận diện bước bằng từ trùng và nghĩa (embedding),
    rồi ghi "Hiểu câu hỏi nói về: ..." để bạn kiểm tra. Tên bước trong mô hình là tiếng Anh, nên
    câu tiếng Việt cần giữ vài từ tiếng Anh của bước.
- **Admin:** xem top-10 chunk, điểm cosine, prompt; bỏ chọn "Gọi LLM" để chỉ xem truy xuất
  (không cần server Kaggle); nút kiểm tra server.

Mỗi lần mở lại notebook server, URL tunnel đổi: sửa `LLM_BASE_URL` rồi khởi động lại Streamlit.

---

## Chạy test

```powershell
pytest
```

Không cần Docker, mạng hay GPU (Qdrant chạy in-memory, model embedding được thay bằng model giả).
Cần đã chạy Bước 1 vì một số test đọc `data/processed/`.

## Lỗi thường gặp

| Hiện tượng | Cách xử lý |
| :--- | :--- |
| `Activate.ps1 cannot be loaded` | Bước 0.2 |
| `check_env` lỗi dòng 2 | Bật Docker Desktop, chạy lại Bước 0.5 |
| `retrieve_top_k` báo collection chứa chunk sai loại | Chạy lại Bước 2 + 3 |
| Notebook Khối 4: `Không thấy ...jsonl` | Chưa Add Input dataset, hoặc dataset thiếu file của thực nghiệm đó |
| Notebook: `CUDA out of memory` | Chưa chọn GPU **T4 x2**; hoặc Restart session rồi chạy lại |
| Notebook: pip in `dependency conflicts` (gradio, diffusers, huggingface-hub) | Chỉ là cảnh báo về gói notebook không dùng. Nếu do bản notebook cũ đã hạ cấp thư viện: **Stop session** rồi bật lại để Kaggle trả môi trường sạch, dùng notebook mới |
| Notebook server Khối 6: `Không mở được link công khai` (bản cũ in `None/v1`) | Đọc log in phía trên. Thêm secret `NGROK_AUTHTOKEN` rồi chạy lại Khối 6 (Bước 7.1 mục 5) |
| Notebook: `Không tải được model` | Đọc dòng `Lần 1/2/3 ... lỗi:` in phía trên. `ConnectionError`/`Temporary failure`: bật Internet, xác minh số điện thoại. `429`/`401`: thêm secret `HF_TOKEN`. `Ổ ... chỉ còn`: Stop session rồi chạy lại |
| Streamlit: "Không gọi được server LLM" | Notebook server đã tắt hoặc URL đổi; xem Bước 7.2. Sai key thì lỗi là 401 |
| Kaggle hết quota GPU (30 giờ/tuần) | Chờ tuần sau; ưu tiên chạy Lần 1, 5, 7 ở Bước 5.3 |
