# HƯỚNG DẪN VIẾT COMMIT 

Tài liệu này hướng dẫn cách viết Git commit rõ ràng và chuyên nghiệp cho dự án của chúng ta.

## Nguyên tắc cốt lõi
Một commit message luôn phải trả lời được một câu hỏi duy nhất: **Bạn vừa thay đổi điều gì?**

## Cấu trúc Commit
`loại_commit: mô tả ngắn gọn`


---

## Các loại Commit (Bắt buộc dùng)

| Loại (Type) | Khi nào sử dụng | Ví dụ |
| :--- | :--- | :--- |
| **`feat`** | Thêm một tính năng hoặc logic mới |
| **`fix`** | Sửa một lỗi (bug) hoặc lỗi SQL | 
| **`chore`** | Cài đặt môi trường, thư mục, dữ liệu mẫu | 
| **`docs`** | Cập nhật tài liệu hoặc file README | 
| **`refactor`**| Tối ưu hóa code (không thêm tính năng mới) 
| **`test`** | Thêm hoặc chỉnh sửa các kịch bản test | 

---

## Quy trình làm việc khuyến nghị
Trước khi gõ lệnh `git commit`, hãy đảm bảo bạn đã làm các bước sau:
1. **Lưu file:** Đảm bảo tất cả các file SQL, Python đã được save (Ctrl+S).
2. **Chạy thử:** Code không bị báo lỗi cú pháp khi chạy ở local.
3. **Stage file:** Chỉ đưa vào vùng chờ (`git add`) những file thực sự liên quan đến commit này.
4. **Commit:** Viết một message rõ ràng theo hướng dẫn trên.

---

## Những File KHÔNG ĐƯỢC Commit (Quy tắc .gitignore)
**TUYỆT ĐỐI KHÔNG** dùng lệnh `git add .` một cách mù quáng. Hãy đảm bảo các file/thư mục sau đã nằm trong `.gitignore` và **không bao giờ** bị đẩy lên kho chứa code:
* **`.env`**: Chứa mật khẩu và cổng kết nối CSDL nhạy cảm. (Chỉ được push file mẫu `.env.example`).
* **`__pycache__/`, `venv/`, `*.pyc`**: Các file biên dịch của Python và thư mục môi trường ảo local.
* **File rác của LaTeX**: Các file `*.aux`, `*.log`, `*.out`, `*.toc`, `*.gz`, `*.fls`, `*.fdb_latexmk` trong thư mục `report/`. Quá trình build file `main.tex` sinh ra rất nhiều file tạm này.
* **Cấu hình IDE/Editor cá nhân**: Thư mục `.vscode/`, `.idea/`, hoặc file `*.swp`. Không đưa cấu hình máy cá nhân lên repo chung.
* **Volume của Database**: Thư mục local nơi Docker lưu trữ dữ liệu vật lý của MySQL (ví dụ: `mysql-data/`). File này rất nặng và chỉ dùng ở máy cá nhân.
* **File rác của Hệ điều hành**: Ví dụ như `.DS_Store` (trên Mac) hay `Thumbs.db` (trên Windows).