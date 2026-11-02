# Yuki 4 - UFM Bot (Đại học Tài chính - Marketing) 🎓

Hệ thống bot tự động cào hoạt động, sự kiện và điểm rèn luyện (ĐRL) từ **Cổng Hoạt Động UFM (HDU)** (`https://hoatdong.ufm.edu.vn`) và thông báo tức thì vào nhóm Zalo 24/7.

---

## 📌 Các Tính Năng Nổi Bật

1. **Bóc tách đa nguồn UFM:**
   - **`/DangKy`:** Bóc tách các hoạt động đang mở đăng ký trực tiếp, theo dõi slot (hết slot / còn slot) và cảnh báo tức thì khi mở thêm slot.
   - **`/Activity/SemesterActivities`:** Theo dõi danh sách hoạt động học kỳ toàn trường được phê duyệt mới nhất.
   - **`/CustomActivity`:** Theo dõi các hoạt động chuyên đề, đối tác tài trợ, công tác xã hội (CTXH).

2. **Cơ chế tự động đăng nhập (Autonomous Relogin):**
   - Khi Cookies ASP.NET Core (`.AspNetCore.Cookies`, `.AspNetCore.Antiforgery`) hết hạn, bot tự động lấy `__RequestVerificationToken`, gửi thông tin đăng nhập với tài khoản `2621008460` và mật khẩu đã lưu, sau đó tự động cập nhật lại `config.json` mà không cần con người can thiệp.

3. **Chống trùng lặp tuyệt đối (Zero Spam / Strict Deduplication):**
   - Cơ chế Baseline ở chu kỳ đầu tiên: Lưu trữ toàn bộ hoạt động hiện có làm mốc cơ sở, không gửi spam vào Zalo.
   - Bảng `delivery_history` được khóa bằng SQLite Triggers ngăn chặn sửa/xóa vĩnh viễn, đối soát từng người nhận và từng bài viết trước khi gửi.

4. **Kênh phân phối Zalo:**
   - Gửi đồng thời tới tài khoản cá nhân Admin (**Trần Lê Phát**) và các nhóm:
     - `demo` (ID: `475259879796859360`)
     - `Tbao , đky sự kiện UFM` (ID: `3790417084788199906`)
     - `Ufm và canh bạc drl` (ID: `2349841347887711204`)
   - Tự động tag `@All` cho các nhóm Zalo.

5. **Cổng Nạp Cookie Cho 100 Sinh Viên (`/submit-cookie`):**
   - Sinh viên chỉ cần mở link trên điện thoại hoặc máy tính, nhập MSSV và dán Cookie.
   - Hệ thống tự động xác thực trực tiếp với Cổng UFM: nếu Cookie hợp lệ mới nạp vào CSDL.
   - Không lo bị khóa tài khoản Zalo cá nhân.

6. **Động Cơ Bắn Đăng Ký Hàng Loạt (Sniper Engine - `batch_register.py`):**
   - Điều phối đa luồng (`ThreadPoolExecutor`) bắn đăng ký cho 100 tài khoản trong **1 – 3 phút**.
   - Tự động trích xuất mã Anti-Forgery `__RequestVerificationToken` độc lập cho từng bạn.
   - Báo cáo chi tiết tiến độ thời gian thực trên Web Dashboard và gửi tổng kết vào Zalo.

7. **Web Dashboard Trực Quan (Port 5004):**
   - Bật / Tắt Bot nhanh bằng công tắc.
   - Tab Quản lý danh sách 100 sinh viên: Bật/Tắt từng bạn, Kiểm tra cookie sống/hết hạn cả lớp.
   - Nút "Bắn Đăng Ký Ngay", "Quét ngay" (Scan now) và "Bắn tin thử" (Test alert).
   - Live Console nhật ký hệ thống.

---

## 🚀 Hướng Dẫn Khởi Chạy

### Cách 1: Chạy trên Windows
Chạy trực tiếp file:
```cmd
start_windows.bat
```
Hoặc chạy lệnh Python:
```bash
python -u run_all.py
```
Truy cập Dashboard tại: [http://localhost:5004](http://localhost:5004)

### Cách 2: Chạy riêng biệt Bot
```bash
python -u bot.py
```

### Cách 3: Chạy riêng Web Dashboard
```bash
python -u web_app.py
```
