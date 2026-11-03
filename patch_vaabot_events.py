import sys
import re

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

vaabot_path = "c:/Users/Admin/Documents/HUIT/vaabot.py"
with open(vaabot_path, "r", encoding="utf-8") as f:
    content = f.read()

initial_cycle_code = '''
def get_initial_cycle(db_file=None):
    """Lấy số thứ tự chu kỳ quét gần nhất từ DB để chu kỳ luôn tăng dần liên tục, không bị reset về #1 khi khởi động lại."""
    try:
        st = database.get_bot_status("scan_cycle", db_file=db_file)
        if st and str(st).isdigit() and int(st) > 0:
            return int(st)
    except Exception:
        pass
    try:
        conn = database.get_connection(db_file)
        cur = conn.cursor()
        cur.execute("SELECT message FROM logs WHERE message LIKE '%Chu kỳ #%' ORDER BY id DESC LIMIT 20")
        rows = cur.fetchall()
        max_c = 0
        for r in rows:
            msg = r[0] if isinstance(r, (tuple, list)) else r["message"]
            m = re.search(r"Chu kỳ #(\\d+)", msg)
            if m:
                c_num = int(m.group(1))
                if c_num > max_c:
                    max_c = c_num
        if max_c > 0:
            return max_c
    except Exception:
        pass
    return 0
'''

if "def get_initial_cycle" not in content:
    content = content.replace("def run_bot():", initial_cycle_code + "\ndef run_bot():")

content = content.replace("    cycle = 0\n    total_new_posts = 0", "    cycle = get_initial_cycle(db_file=DB_TARGET)\n    total_new_posts = 0")

old_scan_start = '''            print(f"👉 ({idx+1}/{len(targets)}) [Bot 2] Đang quét: {page_name}")
            try:
                html = scraper.fetch_url(page_url)
                posts = scraper.parse_posts(html, max_age_hours=max_age_hours, page_url=page_url)
                print(f"   📊 Bóc tách được {len(posts)} bài viết mới (<= {max_age_hours}h).")

                for p in posts:'''

new_scan_start = '''            curr_idx = idx + 1
            total_targets = len(targets)
            print(f"👉 ({curr_idx}/{total_targets}) [Bot 2] Đang quét: {page_name}")
            database.log_event("SCAN", f"🔍 [{curr_idx}/{total_targets}] Đang quét: {page_name}...", db_file=DB_TARGET)
            new_found = 0
            try:
                html = scraper.fetch_url(page_url)
                posts = scraper.parse_posts(html, max_age_hours=max_age_hours, page_url=page_url)
                print(f"   📊 Bóc tách được {len(posts)} bài viết mới (<= {max_age_hours}h).")

                for p in posts:'''

old_seen = '''                    if not database.is_post_seen(ident, content=p["content"], db_file=DB_TARGET):
                        total_new_posts += 1'''

new_seen = '''                    if not database.is_post_seen(ident, content=p["content"], db_file=DB_TARGET):
                        new_found += 1
                        total_new_posts += 1'''

old_sleep = '''            sleep_time = random.uniform(delay_between_pages * 0.8, delay_between_pages * 1.2)
            time.sleep(sleep_time)

        database.set_bot_status("bot_state", "sleeping", db_file=DB_TARGET)
        print(f"💤 Bot 2 hoàn thành vòng #{cycle}. Tạm nghỉ {check_interval} giây trước vòng tiếp theo...")
        database.log_event("SCAN", f"✅ Chu kỳ #{cycle}: Hoàn tất quét {len(targets)} trang mục tiêu. Tạm nghỉ {check_interval}s trước vòng tiếp theo.", db_file=DB_TARGET)'''

new_sleep = '''            sleep_time = random.uniform(delay_between_pages * 0.8, delay_between_pages * 1.2)
            next_str = f"chuyển qua trang [{curr_idx+1}/{total_targets}]" if curr_idx < total_targets else "hoàn tất vòng quét"
            post_stat = f"phát hiện {new_found} bài mới" if new_found > 0 else "0 bài mới"
            database.log_event("SCAN", f"✅ [{curr_idx}/{total_targets}] Hoàn thành: {page_name} ({post_stat}). Nghỉ {int(sleep_time)}s -> {next_str}.", db_file=DB_TARGET)
            time.sleep(sleep_time)

        database.set_bot_status("bot_state", "sleeping", db_file=DB_TARGET)
        print(f"💤 Bot 2 hoàn thành vòng #{cycle}. Tạm nghỉ {check_interval} giây trước vòng tiếp theo...")
        database.log_event("SCAN", f"🎉 Chu kỳ #{cycle}: Hoàn tất quét toàn bộ {len(targets)} trang. Tạm nghỉ {check_interval}s trước chu kỳ #{cycle+1}.", db_file=DB_TARGET)'''

if old_scan_start in content:
    content = content.replace(old_scan_start, new_scan_start, 1)
    content = content.replace(old_seen, new_seen, 1)
    content = content.replace(old_sleep, new_sleep, 1)
    with open(vaabot_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Successfully patched vaabot.py!")
else:
    print("Warning: Could not find exact block in vaabot.py")
