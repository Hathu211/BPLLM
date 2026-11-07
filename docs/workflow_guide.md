# Quy trình làm việc

## 1. Mô hình branch

- **`main`**: nhánh ổn định, không làm việc trực tiếp trên nhánh này.
- **`develop`**: nhánh tích hợp, mọi tính năng làm xong được gộp vào đây.
- **`feat_<tên-chức-năng>`**: nhánh làm việc hằng ngày của từng người.

## 2. Làm việc hằng ngày

**Bước 1: Cập nhật code và tạo nhánh**

```bash
git checkout develop
git pull origin develop
git checkout -b feat_ten_chuc_nang
```

**Bước 2: Viết code và test.** Cấu hình mới (host, cổng, tên model...) đưa vào `src/bpllm/config.py` và `.env.example`, không ghi cứng trong code.

**Bước 3: Kiểm tra lại từ đầu**

Trước khi commit, kiểm tra dự án vẫn chạy được theo đúng các bước trong README:

```bash
docker compose -f docker_compose.yml up -d
python scripts/build_vector_store.py
pytest
streamlit run app/streamlit_app.py
```

`build_vector_store.py` tạo lại collection mỗi lần chạy, nên không cần xóa dữ liệu Qdrant cũ trước.

**Bước 4: Commit và push**

Chỉ add các file liên quan đến task, không dùng `git add .`. Message viết theo [hướng dẫn commit](commit_guide.md).

```bash
git commit -m "feat: mô tả ngắn gọn"
git push origin feat_ten_chuc_nang
```

## 3. Quy trình chung

1. **Dev** push code, tạo PR và yêu cầu Copilot review. Xem xét gợi ý của AI, đúng và hợp lý thì sửa.
2. **Tester** vào PR, kiểm tra và comment trực tiếp vào phần code có lỗi (chỉ ghi lỗi và cách sửa).
3. **Dev** xem lại comment: đúng thì sửa và bấm `resolve`; chưa đồng ý thì comment lại, không sửa, không bấm `resolve`, chờ PM kiểm tra.
4. **PM** kiểm tra lần cuối.

## 4. Quy trình PR

### 4.1. Cập nhật nhánh

Để tránh conflict, gộp code mới nhất từ `develop` vào nhánh của bạn bằng merge:

```bash
git checkout feat_ten_chuc_nang
git merge develop
```

### 4.2. Reviewer kiểm tra kỹ thuật

Reviewer kéo nhánh về và chạy các lệnh ở Bước 3.

- **Chạy tốt:** comment xác nhận đã test thành công, bấm Approve, không merge.
- **Có lỗi:** bấm Request Changes, ghi rõ lỗi và yêu cầu dev sửa.

### 4.3. Trưởng nhóm duyệt cuối

Sau khi reviewer approve, trưởng nhóm kiểm tra nội dung thay đổi, conflict và logic tổng thể. Nếu ổn thì bấm Approve và merge PR vào `develop`.

**Chỉ trưởng nhóm được merge.**

## 5. Điều kiện hoàn thành task

- Dev đã tạo PR đúng template.
- Dev đã gọi Copilot review, tự kiểm tra và sửa lỗi nếu phù hợp.
- Tester đã review code, kéo về chạy thử và kiểm tra lần 2.
- Dev và Tester đã viết đủ report.

## 6. Phát hành

Khi `develop` đã đủ tính năng và chạy ổn định:

```bash
git checkout main
git pull origin main
git merge develop
git push origin main
```
