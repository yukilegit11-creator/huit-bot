import os, sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT_DIR = r"C:\Users\Admin\Documents\HUIT"

# 1. Patch ufm_bot.py
ufm_bot_path = os.path.join(ROOT_DIR, "ufm_bot.py")
with open(ufm_bot_path, "r", encoding="utf-8") as f:
    text = f.read()

# Add alert helper
alert_func = '''ADMIN_ZALO_UID = "7662918962461429024"
last_ufm_admin_alert_time = 0

def alert_admin_ufm_error(zalo_inst, error_title: str, detail_msg: str, throttle_secs: int = 1800):
    global last_ufm_admin_alert_time
    now_ts = time.time()
    if now_ts - last_ufm_admin_alert_time < throttle_secs:
        return
    last_ufm_admin_alert_time = now_ts
    now_vn = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S %d/%m/%Y")
    warn_text = (
        "⚠️ [UFM - CẢNH BÁO LỖI HỆ THỐNG / COOKIE] ⚠️\\n"
        "━━━━━━━━━━━━━━━━━━━━\\n"
        f"🚨 Lỗi: {error_title}\\n"
        f"📌 Chi tiết: {detail_msg}\\n"
        f"⏰ Thời gian: {now_vn}\\n"
        "━━━━━━━━━━━━━━━━━━━━\\n"
        "👉 Vui lòng truy cập Web Dashboard (/bot4) để cập nhật Cookie / kiểm tra ngay!"
    )
    try:
        if not zalo_inst.client:
            zalo_inst.connect()
        if zalo_inst.client:
            zalo_inst.client.send(Message(text=warn_text), thread_id=ADMIN_ZALO_UID, thread_type=ThreadType.USER)
            print(f"🚨 [UFM Alert] Đã gửi thông báo lỗi UFM tới Zalo Trần Lê Phát ({ADMIN_ZALO_UID})")
            database.log_event("WARN", f"Đã gửi cảnh báo '{error_title}' tới Admin qua Zalo.", db_file=DB_TARGET)
    except Exception as ze:
        print(f"❌ [UFM Alert] Không thể gửi cảnh báo Zalo tới Admin: {ze}")
'''

if "alert_admin_ufm_error" not in text:
    idx = text.find("def run_bot():")
    text = text[:idx] + alert_func + "\n" + text[idx:]

# Replace loop processing in ufm_bot.py
loop_target = '''            if not is_ok:
                print(f"⚠️ [Chu kỳ #{cycle}] {msg}")
                database.set_bot_status("portal_cookie_status", "expired", db_file=DB_TARGET)
                database.log_event("WARN", f"Phiên UFM cần đăng nhập lại: {msg}", db_file=DB_TARGET)
            else:'''

loop_repl = '''            if not is_ok:
                print(f"⚠️ [Chu kỳ #{cycle}] {msg}")
                database.set_bot_status("portal_cookie_status", "expired", db_file=DB_TARGET)
                database.log_event("WARN", f"Phiên UFM cần đăng nhập lại: {msg}", db_file=DB_TARGET)
                alert_admin_ufm_error(zalo, "Phiên UFM cần đăng nhập lại", msg)
            else:'''

text = text.replace(loop_target, loop_repl)

# Activity handling replacement
act_block_target = '''                for act in activities:
                    aid = str(act["activity_id"])
                    existing = database.get_seen_activity(aid, db_file=DB_TARGET)

                    if existing is not None:
                        old_is_full = bool(existing.get("is_full", 0))
                        new_is_full = bool(act.get("is_full", False))
                        database.update_activity_status(aid, act.get("status", ""), new_is_full, db_file=DB_TARGET)

                        if old_is_full and not new_is_full and "mở đăng ký" in act.get("status", "").lower():
                            reopened_count += 1
                            log_msg = f"⚡ Phát hiện hoạt động MỞ THÊM SLOT: {act['title']} (+{act['points']} ĐRL)"
                            print(log_msg)
                            database.log_event("ACTIVITY", log_msg, db_file=DB_TARGET)
                            database.add_crawled_activity(act, action_type="REOPENED", is_sent=True, db_file=DB_TARGET)
                            send_zalo_ufm(zalo, act, is_reopened=True)
                            if messenger and config.get("messenger", {}).get("enabled", False):
                                try:
                                    messenger.send_activity_alert(act, is_reopened=True, db_file=DB_TARGET, unit_label="Đơn vị tổ chức")
                                except Exception as me:
                                    print(f"⚠️ [Yuki 4] Lỗi gửi Messenger mở slot: {me}")
                        continue

                    # Hoạt động MỚI 100%
                    new_count += 1
                    database.record_seen_activity(act, is_sent=True, db_file=DB_TARGET)
                    database.add_crawled_activity(act, action_type="NEW", is_sent=True, db_file=DB_TARGET)

                    log_msg = f"🎉 Phát hiện hoạt động MỚI: {act['title']} (+{act['points']} ĐRL)"
                    print(log_msg)
                    database.log_event("ACTIVITY", log_msg, db_file=DB_TARGET)
                    send_zalo_ufm(zalo, act, is_reopened=False)
                    if messenger and config.get("messenger", {}).get("enabled", False):
                        try:
                            messenger.send_activity_alert(act, is_reopened=False, db_file=DB_TARGET, unit_label="Đơn vị tổ chức")
                        except Exception as me:
                            print(f"⚠️ [Yuki 4] Lỗi gửi Messenger bài mới: {me}")

                if new_count > 0 or reopened_count > 0:
                    print(f"✅ [Chu kỳ #{cycle}] Đã xử lý {new_count} bài mới, {reopened_count} bài mở thêm slot.")'''

act_block_repl = '''                for act in activities:
                    aid = str(act["activity_id"])
                    raw_id = str(act.get("raw_id", ""))
                    existing = database.get_seen_activity(aid, db_file=DB_TARGET)
                    if not existing and raw_id:
                        existing = database.get_seen_activity(f"UFM_{raw_id}", db_file=DB_TARGET) or \\
                                   database.get_seen_activity(f"DK_{raw_id}", db_file=DB_TARGET) or \\
                                   database.get_seen_activity(f"SEM_{raw_id}", db_file=DB_TARGET) or \\
                                   database.get_seen_activity(raw_id, db_file=DB_TARGET)

                    if existing is not None:
                        matched_id = existing["activity_id"]
                        old_is_full = bool(existing.get("is_full", 0))
                        new_is_full = bool(act.get("is_full", False))
                        old_status = str(existing.get("status", "") or "").lower()
                        new_status = str(act.get("status", "") or "").lower()
                        old_is_sent = bool(existing.get("is_sent", 0))

                        database.update_activity_status(matched_id, act.get("status", ""), new_is_full, db_file=DB_TARGET)

                        is_now_open = ("mở" in new_status or "còn slot" in new_status) and not new_is_full
                        was_previously_open = ("mở" in old_status or "còn slot" in old_status) and not old_is_full

                        # 1. Trước đó chưa gửi thông báo (Baseline) mà bây giờ ĐANG MỞ ĐĂNG KÝ
                        if not old_is_sent and is_now_open:
                            database.update_seen_is_sent(matched_id, is_sent=True, db_file=DB_TARGET)
                            database.add_crawled_activity(act, action_type="NEW", is_sent=True, db_file=DB_TARGET)
                            log_msg = f"🎉 Phát hiện hoạt động MỚI MỞ ĐĂNG KÝ: {act['title']} (+{act['points']} ĐRL)"
                            print(log_msg)
                            database.log_event("ACTIVITY", log_msg, db_file=DB_TARGET)
                            send_zalo_ufm(zalo, act, is_reopened=False)
                            if messenger and config.get("messenger", {}).get("enabled", False):
                                try:
                                    messenger.send_activity_alert(act, is_reopened=False, db_file=DB_TARGET, unit_label="Đơn vị tổ chức")
                                except Exception as me:
                                    print(f"⚠️ [Yuki 4] Lỗi gửi Messenger: {me}")
                            continue

                        # 2. Trước đó đã đầy (old_is_full == True) và bây giờ mở thêm slot (new_is_full == False)
                        if old_is_full and is_now_open:
                            reopened_count += 1
                            database.add_crawled_activity(act, action_type="REOPENED", is_sent=True, db_file=DB_TARGET)
                            log_msg = f"⚡ Phát hiện hoạt động MỞ THÊM SLOT: {act['title']} (+{act['points']} ĐRL)"
                            print(log_msg)
                            database.log_event("ACTIVITY", log_msg, db_file=DB_TARGET)
                            send_zalo_ufm(zalo, act, is_reopened=True)
                            if messenger and config.get("messenger", {}).get("enabled", False):
                                try:
                                    messenger.send_activity_alert(act, is_reopened=True, db_file=DB_TARGET, unit_label="Đơn vị tổ chức")
                                except Exception as me:
                                    print(f"⚠️ [Yuki 4] Lỗi gửi Messenger mở slot: {me}")
                            continue

                        # 3. Trước đó chưa mở ('Hoạt động học kỳ', 'Chưa mở', ...) và bây giờ MỞ ĐĂNG KÝ
                        if not was_previously_open and is_now_open:
                            database.update_seen_is_sent(matched_id, is_sent=True, db_file=DB_TARGET)
                            database.add_crawled_activity(act, action_type="NEW", is_sent=True, db_file=DB_TARGET)
                            log_msg = f"🔥 Phát hiện hoạt động CHÍNH THỨC MỞ ĐĂNG KÝ: {act['title']} (+{act['points']} ĐRL)"
                            print(log_msg)
                            database.log_event("ACTIVITY", log_msg, db_file=DB_TARGET)
                            send_zalo_ufm(zalo, act, is_reopened=False)
                            if messenger and config.get("messenger", {}).get("enabled", False):
                                try:
                                    messenger.send_activity_alert(act, is_reopened=False, db_file=DB_TARGET, unit_label="Đơn vị tổ chức")
                                except Exception as me:
                                    print(f"⚠️ [Yuki 4] Lỗi gửi Messenger: {me}")
                            continue

                        continue

                    # Hoạt động MỚI 100%
                    new_count += 1
                    database.record_seen_activity(act, is_sent=True, db_file=DB_TARGET)
                    database.add_crawled_activity(act, action_type="NEW", is_sent=True, db_file=DB_TARGET)

                    log_msg = f"🎉 Phát hiện hoạt động MỚI: {act['title']} (+{act['points']} ĐRL)"
                    print(log_msg)
                    database.log_event("ACTIVITY", log_msg, db_file=DB_TARGET)
                    send_zalo_ufm(zalo, act, is_reopened=False)
                    if messenger and config.get("messenger", {}).get("enabled", False):
                        try:
                            messenger.send_activity_alert(act, is_reopened=False, db_file=DB_TARGET, unit_label="Đơn vị tổ chức")
                        except Exception as me:
                            print(f"⚠️ [Yuki 4] Lỗi gửi Messenger bài mới: {me}")

                if new_count > 0 or reopened_count > 0:
                    print(f"✅ [Chu kỳ #{cycle}] Đã xử lý {new_count} bài mới, {reopened_count} bài mở thêm slot.")
                
                # Ghi nhận log chu kỳ quét kèm mốc thời gian rõ ràng
                database.log_event("SCAN", f"🔄 [{now_str}] Chu kỳ #{cycle}: Hoàn tất kiểm tra cổng ĐRL UFM ({len(activities)} hoạt động).", db_file=DB_TARGET)'''

assert act_block_target in text, "act_block_target not found in ufm_bot.py"
text = text.replace(act_block_target, act_block_repl)

# Exception block replacement
exc_target = '''        except Exception as e:
            err_msg = f"Lỗi chu kỳ #{cycle}: {e}"
            print(f"❌ {err_msg}")
            database.log_event("ERROR", err_msg, db_file=DB_TARGET)'''

exc_repl = '''        except Exception as e:
            err_msg = f"Lỗi chu kỳ #{cycle}: {e}"
            print(f"❌ {err_msg}")
            database.log_event("ERROR", err_msg, db_file=DB_TARGET)
            alert_admin_ufm_error(zalo, "Lỗi ngoại lệ chu kỳ quét UFM", err_msg)'''

text = text.replace(exc_target, exc_repl)

with open(ufm_bot_path, "w", encoding="utf-8") as f:
    f.write(text)
print("ufm_bot.py patched successfully!")
