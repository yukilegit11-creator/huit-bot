import re

# 1. Patch scraper.py
p_scraper = r'c:\Users\Admin\Documents\HUIT\scraper.py'
with open(p_scraper, 'r', encoding='utf-8') as f:
    code_s = f.read()

if "self.cookie_expired = False" not in code_s:
    code_s = code_s.replace(
        "self.session.headers.update(DESKTOP_HEADERS)",
        "self.session.headers.update(DESKTOP_HEADERS)\n        self.cookie_expired = False",
        1
    )

if 'self.cookie_expired = True' not in code_s:
    code_s = code_s.replace(
        'print(f"⚠️ Phát hiện Cookie Facebook bị Checkpoint/Hết hạn trên {target_url}. Tự động quét ẩn danh (Guest Mode)...")',
        'self.cookie_expired = True\n                    print(f"⚠️ Phát hiện Cookie Facebook bị Checkpoint/Hết hạn trên {target_url}. Tự động quét ẩn danh (Guest Mode)...")',
        1
    )

with open(p_scraper, 'w', encoding='utf-8') as f:
    f.write(code_s)
print("Patched scraper.py successfully!")

# 2. Helper to add alert_admin_fb_cookie_expired to bot.py
p_bot = r'c:\Users\Admin\Documents\HUIT\bot.py'
with open(p_bot, 'r', encoding='utf-8') as f:
    code_b = f.read()

alert_func_code = '''ADMIN_ZALO_UID = "7581087306337796515"
last_fb_cookie_alert_time = 0

def alert_admin_fb_cookie_expired(zalo_inst, bot_name="Bot 1 (HUIT)", throttle_secs=3600):
    global last_fb_cookie_alert_time
    now_ts = time.time()
    if now_ts - last_fb_cookie_alert_time < throttle_secs:
        return
    last_fb_cookie_alert_time = now_ts
    now_vn = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S %d/%m/%Y")
    warn_text = (
        f"⚠️ [{bot_name} - CẢNH BÁO COOKIE FACEBOOK HẾT HẠN] ⚠️\\n"
        "━━━━━━━━━━━━━━━━━━━━\\n"
        "🚨 Trạng thái: Phiên Cookie Facebook vừa bị đăng xuất hoặc hết hạn!\\n"
        "🌐 Hệ thống: Đã tự động bật Chế độ Ẩn danh (Guest Mode) để tiếp tục quét bài công khai.\\n"
        f"⏰ Thời gian: {now_vn}\\n"
        "━━━━━━━━━━━━━━━━━━━━\\n"
        "👉 Để tối ưu, bạn vui lòng truy cập Web Dashboard (mật khẩu YUKILEGIT0) để dán Cookie mới nhé!"
    )
    try:
        if zalo_inst and zalo_inst.client:
            from zlapi.models import Message, ThreadType
            zalo_inst.client.send(Message(text=warn_text), thread_id=ADMIN_ZALO_UID, thread_type=ThreadType.USER)
            print(f"🚨 Đã gửi cảnh báo Cookie Facebook tới Zalo Admin ({ADMIN_ZALO_UID})")
            database.log_event("WARN", "Đã gửi cảnh báo Cookie Facebook hết hạn tới Zalo Admin.")
    except Exception as e:
        print(f"⚠️ Lỗi gửi cảnh báo Zalo tới Admin: {e}")
'''

if "def alert_admin_fb_cookie_expired" not in code_b:
    code_b = code_b.replace("def get_initial_cycle", alert_func_code + "\ndef get_initial_cycle", 1)

# Inside scan loop in bot.py
if "alert_admin_fb_cookie_expired(zalo" not in code_b:
    code_b = code_b.replace(
        'posts = scraper.parse_posts(html, max_age_hours=max_age_hours, page_url=page_url)',
        'posts = scraper.parse_posts(html, max_age_hours=max_age_hours, page_url=page_url)\n                if getattr(scraper, "cookie_expired", False):\n                    alert_admin_fb_cookie_expired(zalo, bot_name="Bot 1 (HUIT)")',
        1
    )

with open(p_bot, 'w', encoding='utf-8') as f:
    f.write(code_b)
print("Patched bot.py successfully!")

# 3. Patch vaabot.py
p_vaa = r'c:\Users\Admin\Documents\HUIT\vaabot.py'
with open(p_vaa, 'r', encoding='utf-8') as f:
    code_v = f.read()

alert_func_vaa = alert_func_code.replace('bot_name="Bot 1 (HUIT)"', 'bot_name="Bot 2 (VAA)"').replace('database.log_event("WARN", "Đã gửi cảnh báo Cookie Facebook hết hạn tới Zalo Admin.")', 'database.log_event("WARN", "Đã gửi cảnh báo Cookie Facebook hết hạn tới Zalo Admin.", db_file=DB_TARGET)')

if "def alert_admin_fb_cookie_expired" not in code_v:
    code_v = code_v.replace("def get_initial_cycle", alert_func_vaa + "\ndef get_initial_cycle", 1)

if "alert_admin_fb_cookie_expired(zalo" not in code_v:
    code_v = code_v.replace(
        'posts = scraper.parse_posts(html, max_age_hours=max_age_hours, page_url=page_url)',
        'posts = scraper.parse_posts(html, max_age_hours=max_age_hours, page_url=page_url)\n                if getattr(scraper, "cookie_expired", False):\n                    alert_admin_fb_cookie_expired(zalo, bot_name="Bot 2 (VAA)")',
        1
    )

with open(p_vaa, 'w', encoding='utf-8') as f:
    f.write(code_v)
print("Patched vaabot.py successfully!")
