# 🚀 Yuki 2 - VAA Social Feed & 24/7 Zalo Bot (Học Viện Hàng Không Việt Nam)

Hệ thống bóc tách dữ liệu tự động Comet SSR Facebook 24/7 và bắn thông báo trực tiếp vào nhóm/cá nhân Zalo dành riêng cho **Học Viện Hàng Không Việt Nam (VAA / VAU)**.

---

## 👤 Thông Tin Quản Trị Viên & Tác Giả

- **Quản trị viên & Lead Developer:** **Yuki**
- **GitHub:** [`@yukilegit11-creator`](https://github.com/yukilegit11-creator)
- **Hệ thống đồng bộ GitHub:** Tự động Auto-Commit & Auto-Push khi thay đổi cấu hình trên Web Dashboard.

---

## 🏗️ Kiến Trúc Hệ Thống (Độc Lập 100%)

- **`config.json`**: Cấu hình 11 Fanpage/Group VAA, Cookie Facebook, Nhóm Zalo (`demo`), người nhận cá nhân (`Yuki`), bộ lọc từ khóa, thời gian $\le$ 1.0 giờ.
- **`vaabot.db`**: Cơ sở dữ liệu SQLite độc lập lưu trữ bài viết bóc tách, mốc thời gian, trạng thái bot và system logs.
- **`scraper.py`**: Bóc tách Comet SSR Facebook, lọc bài viết $\le$ 1.0 giờ, tự động trích xuất tiêu đề và khối link Form sự kiện (`forms.gle`, `docs.google.com`, v.v.).
- **`zalo_sender.py`**: Chuyển tiếp tin nhắn Zalo hỗ trợ đồng thời cả Nhóm (`@All`) và Cá nhân (tự động loại bỏ `@All` lịch sự).
- **`web_app.py`**: Web Dashboard quản trị hiện đại mang nhận diện VAA chạy trên cổng `5002` (`http://localhost:5002`).
- **`github_sync.py`**: Tự động đồng bộ toàn bộ thay đổi lên GitHub repository.
- **`start_windows.bat`**: Khởi chạy nhanh 1-click cả Web Dashboard và Bot quét trên Windows.

---

## 🚀 Hướng Dẫn Vận Hành

### Chạy trên Windows (1-Click)
Nhấp đúp chuột vào file:
```cmd
start_windows.bat
```
Hoặc chạy lệnh:
```bash
python run_all.py
```
Sau đó truy cập Web Dashboard tại: **`http://localhost:5002`**
