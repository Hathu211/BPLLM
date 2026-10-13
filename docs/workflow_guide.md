

## 1. Kiến trúc Repository & Môi trường
### 1.1. Mô hình Branch
**main** : Nhánh mặc định, không làm việc trên nhánh này.

**develop** : Nhánh tích hợp. Mọi tính năng làm xong sẽ gộp vào đây.

**feature/<tên-chức-năng/cập-nhật>** : Nhánh làm việc hàng ngày của từng dev.

## 2. Daily Code Workflow
**Bước 1**: Cập nhật code mới nhất & Tạo nhánh
```Bash
git checkout develop
git pull origin develop
git checkout -b feature/feature-name
```

**Bước 2**: Code & Áp dụng Rule


**Bước 3**: Kiểm thử nghiêm ngặt với Docker

Trước khi commit, bắt buộc phải test xem DB có build lại từ đầu được không:

```Bash
docker-compose down -v  # -v cực kỳ quan trọng để xóa sạch volume cũ
docker-compose up -d    # Khởi tạo lại DB từ các file 01 -> 99

**Bước 4**: Commit & Push
```bash
# Chỉ add các file liên quan tới task 
# KHÔNG dùng git add .

git commit -m "feat(procedure): ...."
# Với 2 bước trên recommend làm bằng thao tác VSCode, không viết terminal.
```

## 4. Quy trình chung: 
**Bước 1**: Dev push code + tự tạo PR + tự request Copilot AI → AI gợi ý sửa (xem xét, nếu đúng và hợp lý thì sửa).

**Bước 2**: Tester vào PR + check lỗi và comment trực tiếp vào phần code đó (chỉ comment lỗi + cách sửa).

**Bước 3**: Dev vào PR check lại sau kiểm thử: đúng thì sửa, sai thì comment (không sửa theo, chờ PM check final). 

```markdown
Đánh dấu `resolve` với lỗi hợp lý, đã sửa lỗi. 
Những lỗi có vấn đề tuyệt đối không sửa theo và không bấm `resolve`.
```

**Bước 4**: Check final.

## 5. Quy trình PR
### 5.1. Update branch
Để tránh conflict, hãy kéo code mới nhất từ develop về nhánh của bạn:

```Bash
git checkout feature/tao-hoa-don
git merge develop
# (Lưu ý: Dùng merge).
```

### 5.2. Review

Quy trình review gồm **2 bước**:

#### Bước 1: Reviewer kiểm tra kỹ thuật

Người review PR trên GitHub/GitLab bắt buộc kéo nhánh đó về và chạy:

```Bash
docker-compose down -v
docker-compose up --build
```
Xanh (Chạy tốt):
```text
Comment xác nhận đã test thành công.
Bấm Approve (KHÔNG merge).
```
Đỏ (Lỗi SQL / build fail):
```text
Bấm Request Changes.
Ghi rõ lỗi và yêu cầu dev sửa.
```
#### Bước 2: Leader duyệt cuối

Sau khi PR đã được reviewer approve:

```text
Trưởng nhóm kiểm tra lại:
- Nội dung thay đổi
- Conflict
- Logic tổng thể

Nếu ổn:
- Bấm Approve
- Merge PR vào develop
```

**Chỉ trưởng nhóm được phép merge.**

## 6. General checklist for Dev and Tester
Task được tính là (tạm thời) hoàn thành khi:

- Dev đã tạo PR đúng Template.
- Dev đã gọi Copilot review code & tự check, tự sửa lỗi (nếu phù hợp).
- Tester đã review code, pull về chạy thử & check lại lần 2.
- Dev & Tester đã viết đủ report.

## 7. Final
Khi develop đã tích hợp đủ tính năng và chạy Docker trơn tru:

```Bash
git checkout master
git pull origin master
git merge develop
git push origin master
```