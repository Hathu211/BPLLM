# Hướng dẫn viết commit

Một commit message phải trả lời được câu hỏi: **Bạn vừa thay đổi điều gì?**

## Cấu trúc

```text
loại_commit: mô tả ngắn gọn
```

## Các loại commit

| Loại | Khi nào dùng | Ví dụ |
| :--- | :--- | :--- |
| `feat` | Thêm tính năng hoặc logic mới | `feat: thêm chunking cho file BPMN` |
| `fix` | Sửa lỗi | `fix: sửa bộ lọc process khi truy vấn Qdrant` |
| `chore` | Môi trường, thư mục, dữ liệu mẫu | `chore: thêm nhóm cài đặt finetune` |
| `docs` | Tài liệu hoặc README | `docs: viết lại hướng dẫn chạy dự án` |
| `refactor` | Tối ưu code, không thêm tính năng | `refactor: gom cấu hình vào config.py` |
| `test` | Thêm hoặc sửa test | `test: thêm test cho QdrantVectorStore` |

## Trước khi commit

1. Lưu tất cả file.
2. Chạy `pytest` và đảm bảo test đều qua.
3. Chỉ `git add` những file liên quan đến commit này.
4. Viết message theo cấu trúc ở trên.

## Những file không được commit

Không dùng `git add .` khi chưa xem `git status`. Các mục sau không được đưa lên repo:

- **`.env`**: cấu hình riêng của từng máy. Chỉ commit file mẫu `.env.example`.
- **`__pycache__/`, `venv/`, `*.pyc`, `*.egg-info/`, `.pytest_cache/`**: file sinh ra khi cài đặt và chạy Python.
- **`data/qdrant_storage/`, `data/qdrant_local/`**: dữ liệu vector của Qdrant, tạo lại được bằng `scripts/build_vector_store.py`.
- **`*.bin`, `*.safetensors`, `*.pth`, `*.onnx`, `checkpoints/`**: trọng số model.
- **`.vscode/`, `.idea/`**: cấu hình IDE cá nhân.
- **`.DS_Store`, `Thumbs.db`**: file rác của hệ điều hành.
