import os, sys, re

sys.stdout.reconfigure(encoding='utf-8')
ROOT_DIR = r"C:\Users\Admin\Documents\HUIT"

# 1. Update ufm_scraper.py to attach posted_time
for sp_path in [os.path.join(ROOT_DIR, "ufm_scraper.py"), os.path.join(ROOT_DIR, "vaa", "ufm", "ufm_scraper.py")]:
    if not os.path.exists(sp_path):
        continue
    with open(sp_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    if '"posted_time":' not in content:
        content = content.replace(
            '"detail_url": detail_url,',
            '"posted_time": datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S %d/%m/%Y"),\n                    "detail_url": detail_url,'
        )
        with open(sp_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Updated posted_time in {sp_path}")

# 2. Update format_ufm_message and filter in ufm_bot.py
ufm_bot_path = os.path.join(ROOT_DIR, "ufm_bot.py")
with open(ufm_bot_path, "r", encoding="utf-8") as f:
    text = f.read()

# Replace format_ufm_message
old_format = '''def format_ufm_message(act: dict, is_reopened: bool = False, auto_tag_all: bool = True, bot_name: str = "Yuki 4 (UFM ĐRL)") -> str:
    tag_str = "@All\\n" if auto_tag_all else ""
    header = "⚡ [UFM - HOẠT ĐỘNG MỞ THÊM SLOT] ⚡" if is_reopened else "🔥 [UFM - THÔNG BÁO HOẠT ĐỘNG & ĐRL MỚI] 🔥"

    raw_id = act.get("raw_id", "")
    id_prefix = f"[{raw_id}] " if raw_id and not act.get("title", "").startswith(f"[{raw_id}]") else ""
    title = f"{id_prefix}{act.get('title', 'Không có tiêu đề')}"
    unit = act.get("unit", "Chưa rõ đơn vị")
    event_time = act.get("event_time", "Xem chi tiết tại cổng")
    location = act.get("location", "Theo thông báo của đơn vị")
    status = act.get("status", "Đang mở")
    points = act.get("points", 0)
    ctxh = act.get("ctxh", 0)
    group_criteria = act.get("group_criteria", "")
    reg_url = act.get("register_url") or "https://hoatdong.ufm.edu.vn/DangKy"

    lines = [
        f"{tag_str}{header}",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📌 Hoạt động: {title}",
        f"🏢 Đơn vị tổ chức: {unit}"
    ]

    points_str_list = []
    if points > 0:
        points_str_list.append(f"+{points} ĐRL")
    if ctxh > 0:
        points_str_list.append(f"+{ctxh} CTXH")
    if points_str_list:
        lines.append(f"🎯 Điểm: {' | '.join(points_str_list)}")

    if event_time and event_time != "Chưa rõ thời gian":
        lines.append(f"⏰ Thời gian: {event_time}")

    if location and location != "Chưa rõ địa điểm":
        lines.append(f"📍 Địa điểm: {location}")

    if group_criteria:
        lines.append(f"📊 Nhóm: {group_criteria}")

    lines.append(f"👥 Trạng thái: {status}")

    lines.extend([
        "━━━━━━━━━━━━━━━━━━━━",
        "👉 Vào cổng đăng ký ngay:",
        reg_url,
        "━━━━━━━━━━━━━━━━━━━━",
        "🙏 Xin lỗi nếu thông báo này đã làm phiền các bạn!",
        f"🤖 {bot_name}"
    ])

    return "\\n".join(lines)'''

new_format = '''def format_ufm_message(act: dict, is_reopened: bool = False, auto_tag_all: bool = True, bot_name: str = "Yuki 4 (UFM ĐRL)") -> str:
    tag_str = "@All\\n" if auto_tag_all else ""
    header = "⚡ [UFM - HOẠT ĐỘNG MỞ THÊM SLOT] ⚡" if is_reopened else "🔥 [UFM - THÔNG BÁO HOẠT ĐỘNG & ĐRL MỚI] 🔥"

    raw_id = act.get("raw_id", "")
    id_prefix = f"[{raw_id}] " if raw_id and not act.get("title", "").startswith(f"[{raw_id}]") else ""
    title = f"{id_prefix}{act.get('title', 'Không có tiêu đề')}"
    unit = act.get("unit", "Chưa rõ đơn vị")
    event_time = act.get("event_time", "Xem chi tiết tại cổng")
    location = act.get("location", "Theo thông báo của đơn vị")
    status = act.get("status", "Đang mở")
    points = float(act.get("points", 0) or 0)
    ctxh = float(act.get("ctxh", 0) or 0)
    group_criteria = act.get("group_criteria", "")
    reg_url = act.get("register_url") or "https://hoatdong.ufm.edu.vn/DangKy"
    now_vn = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S %d/%m/%Y")
    posted_time = act.get("posted_time") or act.get("first_seen") or now_vn

    lines = [
        f"{tag_str}{header}",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📌 Hoạt động: {title}",
        f"🏢 Đơn vị tổ chức: {unit}"
    ]

    points_str_list = []
    if points > 0:
        points_str_list.append(f"+{points:g} ĐRL")
    if ctxh > 0:
        points_str_list.append(f"+{ctxh:g} CTXH")
    if points_str_list:
        lines.append(f"🎯 Điểm: {' • '.join(points_str_list)}")

    lines.append(f"⏰ Thời gian đăng bài: {posted_time}")

    if event_time and event_time != "Chưa rõ thời gian":
        lines.append(f"📅 Thời gian diễn ra: {event_time}")

    if location and location != "Chưa rõ địa điểm":
        lines.append(f"📍 Địa điểm: {location}")

    if group_criteria:
        lines.append(f"📊 Nhóm: {group_criteria}")

    lines.append(f"👥 Trạng thái: {status}")

    lines.extend([
        "━━━━━━━━━━━━━━━━━━━━",
        "👉 Vào cổng đăng ký ngay:",
        reg_url,
        "━━━━━━━━━━━━━━━━━━━━",
        "🙏 Xin lỗi nếu thông báo này đã làm phiền các bạn!",
        f"🤖 {bot_name}"
    ])

    return "\\n".join(lines)'''

if old_format in text:
    text = text.replace(old_format, new_format)
    print("Patched format_ufm_message in ufm_bot.py")

# Add filter check in ufm_bot.py loop
old_loop_for = '''                for act in activities:
                    aid = str(act["activity_id"])
                    raw_id = str(act.get("raw_id", ""))'''

new_loop_for = '''                for act in activities:
                    aid = str(act["activity_id"])
                    raw_id = str(act.get("raw_id", ""))

                    # ĐIỀU KIỆN LỌC BẮT BUỘC: Chỉ gửi thông báo nếu có ĐRL > 0 hoặc CTXH > 0
                    points_val = float(act.get("points", 0) or 0)
                    ctxh_val = float(act.get("ctxh", 0) or 0)
                    if points_val <= 0 and ctxh_val <= 0:
                        database.record_seen_activity(act, is_sent=False, db_file=DB_TARGET)
                        continue'''

if old_loop_for in text:
    text = text.replace(old_loop_for, new_loop_for)
    print("Added points/ctxh filter in ufm_bot.py")

with open(ufm_bot_path, "w", encoding="utf-8") as f:
    f.write(text)

# 3. Update vaa/ufm/bot.py
vaa_bot_path = os.path.join(ROOT_DIR, "vaa", "ufm", "bot.py")
with open(vaa_bot_path, "r", encoding="utf-8") as f:
    v_text = f.read()

old_v_loop_for = '''                for act in activities:
                    aid = str(act["activity_id"])
                    raw_id = str(act.get("raw_id", ""))'''

new_v_loop_for = '''                for act in activities:
                    aid = str(act["activity_id"])
                    raw_id = str(act.get("raw_id", ""))

                    # ĐIỀU KIỆN LỌC BẮT BUỘC: Chỉ gửi thông báo nếu có ĐRL > 0 hoặc CTXH > 0
                    points_val = float(act.get("points", 0) or 0)
                    ctxh_val = float(act.get("ctxh", 0) or 0)
                    if points_val <= 0 and ctxh_val <= 0:
                        database.record_seen_activity(act, is_sent=False)
                        continue'''

if old_v_loop_for in v_text:
    v_text = v_text.replace(old_v_loop_for, new_v_loop_for)
    with open(vaa_bot_path, "w", encoding="utf-8") as f:
        f.write(v_text)
    print("Added points/ctxh filter in vaa/ufm/bot.py")

# 4. Update format_ufm_message in vaa/ufm/zalo_sender.py
vaa_zalo_path = os.path.join(ROOT_DIR, "vaa", "ufm", "zalo_sender.py")
with open(vaa_zalo_path, "r", encoding="utf-8") as f:
    z_text = f.read()

old_z_format = '''    points_str_list = []
    if points > 0:
        points_str_list.append(f"+{points} ĐRL")
    if ctxh > 0:
        points_str_list.append(f"+{ctxh} CTXH")
    if points_str_list:
        lines.append(f"🎯 Điểm: {' | '.join(points_str_list)}")

    if event_time and event_time != "Chưa rõ thời gian":
        lines.append(f"⏰ Thời gian: {event_time}")'''

new_z_format = '''    now_vn = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S %d/%m/%Y")
    posted_time = act.get("posted_time") or act.get("first_seen") or now_vn

    points_str_list = []
    if points > 0:
        points_str_list.append(f"+{points:g} ĐRL")
    if ctxh > 0:
        points_str_list.append(f"+{ctxh:g} CTXH")
    if points_str_list:
        lines.append(f"🎯 Điểm: {' • '.join(points_str_list)}")

    lines.append(f"⏰ Thời gian đăng bài: {posted_time}")

    if event_time and event_time != "Chưa rõ thời gian":
        lines.append(f"📅 Thời gian diễn ra: {event_time}")'''

if old_z_format in z_text:
    z_text = z_text.replace(old_z_format, new_z_format)
    with open(vaa_zalo_path, "w", encoding="utf-8") as f:
        f.write(z_text)
    print("Patched format_ufm_message in vaa/ufm/zalo_sender.py")

# 5. Update messenger_sender.py format
msgr_path = os.path.join(ROOT_DIR, "messenger_sender.py")
with open(msgr_path, "r", encoding="utf-8") as f:
    m_text = f.read()

old_m_format = '''    points_str_list = []
    if points > 0:
        points_str_list.append(f"+{points} ĐRL")
    if ctxh > 0:
        points_str_list.append(f"+{ctxh} CTXH")
    if semester:
        points_str_list.append(f"HK: {semester}")

    if points_str_list:
        lines.append(f"🎯 Điểm: {' | '.join(points_str_list)}")

    if event_time and event_time != "Chưa rõ thời gian":
        lines.append(f"⏰ Thời gian: {event_time}")'''

new_m_format = '''    now_vn = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S %d/%m/%Y")
    posted_time = act.get("posted_time") or act.get("first_seen") or now_vn

    points_str_list = []
    if points > 0:
        points_str_list.append(f"+{points:g} ĐRL")
    if ctxh > 0:
        points_str_list.append(f"+{ctxh:g} CTXH")
    if semester:
        points_str_list.append(f"HK: {semester}")

    if points_str_list:
        lines.append(f"🎯 Điểm: {' • '.join(points_str_list)}")

    lines.append(f"⏰ Thời gian đăng bài: {posted_time}")

    if event_time and event_time != "Chưa rõ thời gian":
        lines.append(f"📅 Thời gian diễn ra: {event_time}")'''

if old_m_format in m_text:
    m_text = m_text.replace(old_m_format, new_m_format)
    with open(msgr_path, "w", encoding="utf-8") as f:
        f.write(m_text)
    print("Patched format_activity_messenger_message in messenger_sender.py")

print("All files patched with filter and timestamp successfully!")
