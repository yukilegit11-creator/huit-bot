import urllib.request
import json
import sys
import ssl
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding='utf-8')

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

now_vn = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S %d/%m/%Y")
DEMO_GROUP_ID = "7456361874031804652"

print("=== 1. SENDING NOTIFICATION TO DEMO GROUP ABOUT ADDED FB TARGET ===")

confirm_msg = (
    f"@All\n"
    f"🔔 [HỆ THỐNG 4 BOT YUKI - THÔNG BÁO] 🔔\n"
    f"━━━━━━━━━━━━━━━━━━━━\n"
    f"✅ ĐÃ ADD THÀNH CÔNG NGUỒN QUÉT FACEBOOK:\n"
    f"👤 Nguồn: Yu Ki (FB Profile)\n"
    f"🔗 Link: https://www.facebook.com/profile.php?id=61595329828799\n"
    f"🆔 UID: 61595329828799\n"
    f"⏰ Thời gian: {now_vn}\n"
    f"━━━━━━━━━━━━━━━━━━━━\n"
    f"🧪 TÍNH NĂNG MỚI ĐÃ SẴN SÀNG:\n"
    f"1️⃣ Gửi tin test từng nhóm riêng lẻ trên Web Dashboard của cả 4 Bot\n"
    f"2️⃣ Bảng '🧪 Test Nhóm Zalo (4 Bot)' trên thanh điều hướng\n"
    f"3️⃣ Lệnh chat trực tiếp trong Zalo: /listgroup , /test <tên nhóm> , /testall"
)

payload = {
    "bot_id": "bot1",
    "target_id": DEMO_GROUP_ID,
    "target_type": "GROUP",
    "target_name": "demo",
    "custom_message": confirm_msg
}

req = urllib.request.Request(
    "http://180.93.125.40:8000/api/zalo/send-test-target",
    data=json.dumps(payload).encode('utf-8'),
    headers={"Content-Type": "application/json"}
)

try:
    with urllib.request.urlopen(req, context=ctx, timeout=15) as res:
        data = json.loads(res.read().decode('utf-8'))
        print(f"✅ Demo Alert Response ({res.status}): {data}")
except Exception as e:
    print(f"❌ Error sending demo alert: {e}")

print("\n=== 2. TESTING INDIVIDUAL TEST SENDS FOR EACH OF THE 4 BOTS ===")

test_bots = [
    {"bot_id": "bot1", "name": "Bot 1 - HUIT", "target_id": DEMO_GROUP_ID, "target_name": "demo"},
    {"bot_id": "bot2", "name": "Bot 2 - VAA", "target_id": DEMO_GROUP_ID, "target_name": "demo"},
    {"bot_id": "bot3", "name": "Bot 3 - IUH", "target_id": DEMO_GROUP_ID, "target_name": "demo"},
    {"bot_id": "bot4", "name": "Bot 4 - UFM", "target_id": DEMO_GROUP_ID, "target_name": "demo"}
]

for b in test_bots:
    p = {
        "bot_id": b["bot_id"],
        "target_id": b["target_id"],
        "target_type": "GROUP",
        "target_name": b["target_name"],
        "custom_message": f"🧪 [TEST RIÊNG] Tín hiệu kiểm tra kết nối từ {b['name']} tới nhóm {b['target_name']} lúc {now_vn} thành công 100%!"
    }
    r = urllib.request.Request(
        "http://180.93.125.40:8000/api/zalo/send-test-target",
        data=json.dumps(p).encode('utf-8'),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(r, context=ctx, timeout=15) as resp:
            d = json.loads(resp.read().decode('utf-8'))
            print(f"  ✅ [{b['name']}] Status: {resp.status} - Message: {d.get('message')}")
    except Exception as err:
        print(f"  ❌ [{b['name']}] Error: {err}")

print("\nAll tests finished!")
