import sys
import os

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

root_dir = r"c:\Users\Admin\Documents\HUIT"
sys.path.insert(0, root_dir)

from zalo_sender import ZaloDispatcher

print("🚀 Đang khởi tạo ZaloDispatcher để gửi thử thông báo vào nhóm demo...")

dispatcher = ZaloDispatcher(os.path.join(root_dir, "config.json"))
ok, msg = dispatcher.send_demo_group_alert()

print("KẾT QUẢ GỬI THỬ:")
print(f"Trạng thái: {'Thành công' if ok else 'Thất bại'}")
print(f"Chi tiết: {msg}")
