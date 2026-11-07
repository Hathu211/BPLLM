# BPLLM

Trợ lý hỏi đáp về quy trình nghiệp vụ, trả lời dựa trên mô hình BPMN. Dự án dùng Qdrant làm vector database, sentence-transformers để tạo embedding và Streamlit làm giao diện.

## Yêu cầu

- Python 3.10 đến 3.12
- Docker Desktop

## Cài đặt

Chạy một lần ở thư mục gốc của repo (lệnh dành cho PowerShell trên Windows):

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Cấu hình có sẵn giá trị mặc định chạy được ngay. Chỉ cần tạo `.env` khi muốn đổi host, cổng, tên collection hoặc model: sao chép `.env.example` thành `.env` rồi sửa.

## Chạy dự án

**1. Bật Qdrant**

```bash
docker compose -f docker_compose.yml up -d
```

**2. Tạo index.** Lần đầu chạy sẽ tải model embedding nên cần có mạng.

```bash
python scripts/build_vector_store.py
```

**3. Chạy test.** Bước này không cần Docker và không cần tải model.

```bash
pytest
```

**4. Mở giao diện**

```bash
streamlit run app/streamlit_app.py
```

Dữ liệu Qdrant nằm trong `data/qdrant_storage/` và không được commit. Nếu thư mục này trống, chạy lại bước 2.

## Nhóm cài đặt tùy chọn

| Nhóm | Lệnh | Dùng cho |
| :--- | :--- | :--- |
| `dev` | `pip install -e ".[dev]"` | Chạy test |
| `llm` | `pip install -e ".[llm]"` | Gọi LLM qua OpenAI API |
| `finetune` | Xem mục bên dưới | Fine-tune trên Google Colab, không cài trên máy local |

## Fine-tune trên Google Colab

Fine-tune chạy trên GPU của Colab nên máy local không cần các thư viện này. Trên Colab chỉ cài đúng nhóm thư viện fine-tune, không cài cả project, vì project còn kéo theo Streamlit, LangChain, Qdrant và ghim `numpy<2`:

```bash
!pip install "peft>=0.11.0,<0.12.0" "trl>=0.9.0,<0.10.0" "bitsandbytes>=0.43.0,<0.44.0" "accelerate>=0.33.0,<0.34.0"
```

Dữ liệu huấn luyện nằm ở `data/dataset/supervised_finetune_data.json`. Lưu checkpoint lên Google Drive hoặc nơi lưu trữ model, không commit vào repo.

## Cấu trúc thư mục

| Đường dẫn | Nội dung |
| :--- | :--- |
| `src/bpllm/` | Package chính; `config.py` là nơi duy nhất đọc cấu hình |
| `scripts/` | Tạo index, kiểm tra môi trường, chuẩn bị dữ liệu fine-tune |
| `app/` | Giao diện Streamlit |
| `data/raw/` | File BPMN và mô tả quy trình gốc |
| `data/ground_truth/` | Dữ liệu quy trình dùng để tạo index |
| `tests/` | Test pytest |
| `docs/` | Quy trình làm việc của nhóm |

Khi gặp lỗi môi trường, chạy `python scripts/check_env.py` để kiểm tra thư viện, kết nối Qdrant và model embedding.

## Tài liệu

- [Quy trình làm việc](docs/workflow_guide.md)
- [Hướng dẫn viết commit](docs/commit_guide.md)
