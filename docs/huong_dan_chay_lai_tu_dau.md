# Hướng dẫn xóa sạch và chạy lại dự án BPLLM từ đầu

Mục tiêu: xóa mọi thứ do script hoặc công cụ tự sinh ra (môi trường ảo, Docker, dữ liệu đã chuẩn hóa, ground truth, vector store...), rồi chạy lại từng bước để kiểm tra:
1. Từ một máy "sạch", dự án có dựng lên trơn tru không.
2. Các script có tự sinh lại đúng những file đã xóa không.
3. File sinh lại có **giống hệt** bản trước khi xóa không.

> Mọi lệnh bên dưới chạy trong **PowerShell**, tại thư mục gốc của dự án:
> ```powershell
> cd D:\BPLLM\BPLLM1
> ```

---

## 0. Chuẩn bị

| Cần có | Cách kiểm tra |
| :--- | :--- |
| Docker Desktop đang chạy (biểu tượng cá voi màu xanh) | `docker version` in ra cả phần Client và Server |
| Python **3.11** (file `test_project_setup.py` dùng `tomllib`, mà `tomllib` chỉ có từ 3.11) | `py -3.11 --version` |
| Có mạng (để tải thư viện, image Qdrant và model embedding) | |

Đóng mọi terminal hoặc VS Code đang dùng `venv` của dự án. Nếu không, Windows sẽ không cho xóa thư mục `venv`.

---

## 1. Sao lưu file tự sinh để đối chiếu sau

Bước này **không bắt buộc, nhưng nên làm**: đây là cách duy nhất để chứng minh script sinh lại đúng.

```powershell
$backup = "D:\BPLLM\_backup_truoc_khi_xoa"
New-Item "$backup\data" -ItemType Directory -Force | Out-Null
Copy-Item data\processed, data\ground_truth, data\dataset "$backup\data" -Recurse -Force
Get-ChildItem $backup -Recurse -File | Measure-Object | Select-Object Count
```

Bản sao lưu nằm **ngoài** thư mục dự án nên không bị xóa ở bước 3.

---

## 2. Dừng và xóa Qdrant trong Docker

```powershell
docker compose -f docker_compose.yml down
```

Lệnh này dừng và xóa container `bpllm-qdrant`. Phải dừng trước thì mới xóa được `data\qdrant_storage` ở bước 3, vì container đang giữ file trong đó.

Nếu muốn kiểm tra cả việc tải image từ đầu (tùy chọn):

```powershell
docker image rm qdrant/qdrant:v1.10.1
```

---

## 3. Xóa toàn bộ file tự sinh

### 3.1. Những gì sẽ xóa và những gì phải giữ

| XÓA (tự sinh lại được) | Sinh lại bằng |
| :--- | :--- |
| `venv\` | `python -m venv` (bước 4) |
| `src\bpllm.egg-info\` | `pip install -e .` (bước 4) |
| `__pycache__\`, `.pytest_cache\` | Python và pytest tự tạo |
| `data\qdrant_storage\` | Docker (bước 5) và `build_vector_store.py` (bước 9.1) |
| `data\processed\*` (graph, file DFG, BPMN đã làm sạch, report, `bpmn_chunks.jsonl
`) | `prepare_processes.py` (bước 6) và `chunking_processor` (bước 9.2) |
| `data\ground_truth\*.json` | `generate_ground_truth.py` (bước 6) |
| `data\dataset\supervised_finetune_data.json` | `prepare_dataset.py` (bước 9.3) |

| **GIỮ NGUYÊN, KHÔNG XÓA** (dữ liệu đầu vào, không script nào sinh lại được) |
| :--- |
| `data\raw\original\*.bpmn`: BPMN gốc của 3 quy trình |
| `data\raw\*.bpmn`: bản đối chiếu, `prepare_processes.py` dùng để kiểm tra chéo |
| `data\raw\food_delivery_dfg_*.txt`: file natural text gốc của bài báo |
| `data\questions\*`: bộ câu hỏi benchmark |
| `src\`, `scripts\`, `tests\`, `app\`, `docs\`, `pyproject.toml`, `docker_compose.yml`, `.env` (nếu có) |

### 3.2. Lệnh xóa

```powershell
# Môi trường ảo và file build
Remove-Item venv, src\bpllm.egg-info, .pytest_cache -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem src, scripts, tests, app -Recurse -Directory -Filter __pycache__ |
  Remove-Item -Recurse -Force

# Dữ liệu tự sinh (giữ lại các thư mục rỗng)
Remove-Item data\qdrant_storage -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item data\processed\* -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item data\ground_truth\*.json -Force -ErrorAction SilentlyContinue
Remove-Item data\dataset\supervised_finetune_data.json -Force -ErrorAction SilentlyContinue
```

### 3.3. Kiểm tra đã sạch

```powershell
Test-Path venv, data\qdrant_storage            # cả hai phải là False
(Get-ChildItem data\processed -Recurse -File).Count   # phải là 0
(Get-ChildItem data\ground_truth -File).Count         # phải là 0
Get-ChildItem data\raw -Recurse -File | Select-Object Name   # phải còn đủ 9 file đầu vào
```

`data\raw` phải còn: `ecommerce.bpmn`, `food_delivery.bpmn`, `reimbursement.bpmn`, `food_delivery_dfg_activities.txt`, `food_delivery_dfg_flows.txt`, và 3 file `.bpmn` trong `original\`.

---

## 4. Tạo lại môi trường ảo

```powershell
py -3.11 -m venv venv

# Nếu Activate.ps1 bị chặn ("running scripts is disabled"), chạy dòng này trước (chỉ áp dụng cho cửa sổ hiện tại):
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

**Kiểm tra đang dùng đúng Python của venv.** Đây chính là nguyên nhân hay gây lỗi `No module named 'bpllm'`:

```powershell
python -c "import sys, bpllm; print(sys.executable)"
```

Kết quả phải là `D:\BPLLM\BPLLM1\venv\Scripts\python.exe`. Nếu ra `...\AppData\Local\Programs\Python\Python311\python.exe`, nghĩa là venv **chưa được bật**: chạy lại `venv\Scripts\Activate.ps1`. Khi venv đã bật, đầu dòng lệnh sẽ có chữ `(venv)`.

---

## 5. Bật Qdrant và kiểm tra môi trường

```powershell
docker compose -f docker_compose.yml up -d
docker ps --filter name=bpllm-qdrant     # STATUS phải là "Up ..."
```

Mở http://localhost:6333/dashboard: phải thấy trang Qdrant, chưa có collection nào.

```powershell
python scripts/check_env.py
```

Lần đầu chạy sẽ tải model `all-MiniLM-L6-v2`, mất khoảng 1–2 phút. Kết quả đúng có 3 dòng thành công và kết thúc bằng:

```
TẤT CẢ MÔI TRƯỜNG VÀ HẠ TẦNG ĐÃ SẴN SÀNG 100%!
```

---

## 6. Phase 1: chuẩn hóa dữ liệu

> Chú ý tên file: `prepare_process`**`es`**`.py`, có thêm "es".

```powershell
python scripts/prepare_processes.py
```

Kết quả đúng (2 dòng `!` của E-commerce là **cảnh báo bình thường**: BPMN gốc thiếu nhãn ở 2 nhánh, không phải lỗi):

```
[OK ] ecommerce: {'activities': 15, 'exclusive_gateways': 4, 'parallel_gateways': 0, 'start_events': 1, 'end_events': 1, 'sequence_flows': 22}
      ! gateway 'Is this a new customer?': nhánh không có nhãn điều kiện tới ['Recover client history']
      ! gateway 'Is the courier available?': nhánh không có nhãn điều kiện tới ['Assign package to courier']
[OK ] food_delivery: {'activities': 17, 'exclusive_gateways': 4, 'parallel_gateways': 2, 'start_events': 1, 'end_events': 1, 'sequence_flows': 27}
[OK ] reimbursement: {'activities': 11, 'exclusive_gateways': 5, 'parallel_gateways': 0, 'start_events': 1, 'end_events': 2, 'sequence_flows': 20}
Đã ghi kết quả vào D:\BPLLM\BPLLM1\data\processed
```

```powershell
python scripts/generate_ground_truth.py
python scripts/generate_ground_truth.py --check
```

Kết quả đúng:

```
[OK ] ecommerce: 15 activity, 4 gateway, 22 flow
[OK ] food_delivery: 17 activity, 6 gateway, 27 flow
[OK ] reimbursement: 11 activity, 5 gateway, 20 flow
[OK ] ecommerce
[OK ] food_delivery
[OK ] reimbursement
```

**Kiểm tra file đã được sinh ra:**

```powershell
Get-ChildItem data\processed, data\ground_truth -Recurse -File | Select-Object FullName
```

Phải có 19 file:
- `data\processed\phase1_report.json`
- Mỗi quy trình 6 file trong `data\processed\<quy_trình>\`: `<quy_trình>.bpmn`, `graph.json`, `dfg_activities.txt`, `dfg_flows_paper.txt`, `dfg_flows_full.txt`, `dfg_flows_gateway.txt`
- 3 file `data\ground_truth\<quy_trình>.json`

---

## 7. Chạy test

```powershell
pytest
```

Tất cả test phải **pass**. Test không cần Docker và không cần tải model. Lệnh này chạy các test: chunking, embedder, qdrant, config và project setup.

**Kiểm tra Phase 1** (không cần pytest):

```powershell
python scripts/generate_ground_truth.py --check
```

Phải in `[OK ]` cho cả 3 quy trình.

> 2 file test Phase 1 (`tests/test_parsing.py`, `tests/test_phase1_pipeline.py`) không có trên git: chúng nằm trong `.gitignore`. Nếu máy bạn còn 2 file này, có thể tự chạy thêm `pytest tests/test_parsing.py tests/test_phase1_pipeline.py -q`. Kết quả đúng là `111 passed`.

---

## 8. Đối chiếu với bản sao lưu ở bước 1

```powershell
$backup = "D:\BPLLM\_backup_truoc_khi_xoa"
$root = (Resolve-Path .).Path
Get-ChildItem data\processed, data\ground_truth -Recurse -File | ForEach-Object {
  $rel = $_.FullName.Substring($root.Length + 1)
  $old = Join-Path $backup $rel
  if (-not (Test-Path $old)) { "MOI    $rel" }
  elseif ((Get-FileHash $_.FullName).Hash -eq (Get-FileHash $old).Hash) { "GIONG  $rel" }
  else { "KHAC   $rel" }
}
```

**Kết quả mong đợi:** mọi file của Phase 1 đều là `GIONG`. Như vậy chuẩn hóa là **tất định**: cùng đầu vào thì luôn ra cùng một kết quả.

- Nếu có dòng `KHAC`, xem chi tiết bằng `git diff --no-index "$backup\<đường_dẫn>" "<đường_dẫn>"`.
- `bpmn_chunks.jsonl' chỉ xuất hiện sau bước 9.2, nên ở bước này nó không có trong danh sách. Đây là điều bình thường.

---

## 9. (Tùy chọn) Chạy tiếp các bước sau Phase 1

### 9.1. Tạo vector store (cần Qdrant đang chạy)

```powershell
python scripts/build_vector_store.py
```

Kết thúc bằng `VECTOR STORE INDEXING COMPLETED SUCCESSFULLY!`. Trên dashboard http://localhost:6333/dashboard sẽ thấy collection `bpllm_processes`.

### 9.2. Sinh lại `bpmn_chunks_jsonl`

```powershell
python -m bpllm.chunking.chunking_processor
```

Lệnh này phải chạy ở thư mục gốc dự án, vì script đọc đường dẫn tương đối `./data/raw`.

### 9.3. Sinh lại dữ liệu fine-tune

```powershell
python scripts/prepare_dataset.py
```

Lưu ý: file này sẽ **khác** bản cũ trong git. Đây là điều đúng, không phải lỗi: ground truth giờ có thêm khóa `dfg_activities`, nên phần context trong từng mẫu cũng thay đổi theo.

### 9.4. Mở giao diện

```powershell
streamlit run app/streamlit_app.py
```

---

## 10. Lỗi thường gặp

| Thông báo lỗi | Nguyên nhân | Cách xử lý |
| :--- | :--- | :--- |
| `can't open file '...\scripts\prepare_process.py'` | Gõ sai tên file | Tên đúng là `prepare_processes.py` |
| `No module named 'bpllm'` hoặc `No module named 'dotenv'` | Đang dùng Python ngoài venv | Chạy `venv\Scripts\Activate.ps1`, rồi kiểm tra lại như ở bước 4 |
| `running scripts is disabled on this system` | PowerShell chặn file `.ps1` | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |
| `ModuleNotFoundError: No module named 'tomllib'` | Venv dùng Python 3.10 | Xóa venv, tạo lại bằng `py -3.11 -m venv venv` |
| `Remove-Item ... being used by another process` | Còn terminal hoặc VS Code đang dùng venv, hoặc Qdrant đang giữ `qdrant_storage` | Gõ `deactivate`, đóng VS Code, chạy `docker compose ... down` rồi xóa lại |
| `error during connect` / `cannot find the file specified` khi chạy docker | Docker Desktop chưa bật | Mở Docker Desktop, chờ trạng thái "Engine running" |
| `Bind for 0.0.0.0:6333 failed: port is already allocated` | Một container Qdrant khác đang dùng cổng | `docker ps`, rồi `docker stop <tên>`; hoặc đổi `QDRANT_HTTP_PORT` trong `.env` |
| `prepare_processes.py` in `[LỖI]` và trả exit code 1 | File BPMN trong `data\raw` bị sửa hoặc hỏng | Đọc dòng `-` ngay bên dưới để biết phần tử nào sai; khôi phục bằng `git checkout -- data/raw` |

---

## 11. Checklist

- [ ] Bước 1: đã sao lưu sang `D:\BPLLM\_backup_truoc_khi_xoa`
- [ ] Bước 3: `data\processed` và `data\ground_truth` rỗng; `data\raw` còn đủ 9 file
- [ ] Bước 4: `sys.executable` trỏ vào `venv\Scripts\python.exe`
- [ ] Bước 5: `check_env.py` báo sẵn sàng 100%
- [ ] Bước 6: 3 quy trình `[OK ]`, `--check` OK, có đủ 19 file
- [ ] Bước 7: `pytest` pass hết, `generate_ground_truth.py --check` in OK cả 3 quy trình
- [ ] Bước 8: mọi file Phase 1 đều `GIONG` với bản sao lưu
- [ ] (Tùy chọn) Bước 9: vector store, file chunk, dataset và Streamlit đều chạy được

Khi đã xong và mọi thứ đều đúng, có thể xóa bản sao lưu:
`Remove-Item D:\BPLLM\_backup_truoc_khi_xoa -Recurse -Force`
