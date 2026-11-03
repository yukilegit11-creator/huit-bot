import json, time
from iuh_bot import send_zalo_iuh, DB_TARGET
from zalo_sender import ZaloDispatcher
import database

# 1. Connect Zalo
zalo = ZaloDispatcher('/root/huit-bot/config_iuh.json', db_file=DB_TARGET)
zalo.bot_name = "Yuki 3 (IUH ĐRL)"
ok = zalo.connect()
print("Zalo connected:", ok)

# 2. Activity 4286 data
act_4286 = {
    "activity_id": "4286",
    "title": "Tham gia cổ vũ Đội Văn nghệ Khoa Công nghệ Cơ khí dự thi Hội diễn Văn nghệ Sinh viên năm 2026 (300/300)",
    "semester": "1/2026 - 2027",
    "points": 2.0,
    "deadline": "05-11-2026",
    "status": "Đã đủ số lượng",
    "slots": "300/300",
    "details": "https://doantn.iuh.edu.vn/doanvien.html"
}

# 3. Send
print("Broadcasting activity 4286...")
res = send_zalo_iuh(zalo, act_4286, is_reopened=False)
print("Result of send_zalo_iuh:", res)

# 4. Update seen_activities is_sent = 1
database.update_seen_is_sent("4286", is_sent=True, db_file=DB_TARGET)
print("Updated seen_activities is_sent=1 for 4286")
