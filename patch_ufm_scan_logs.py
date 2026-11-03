import re

def patch_file(p):
    with open(p, "r", encoding="utf-8") as f:
        code = f.read()

    # 1. Add get_initial_cycle before run_bot
    if "def get_initial_cycle" not in code:
        get_c_func = '''def get_initial_cycle(db_file=None):
    """Lấy số thứ tự chu kỳ quét gần nhất từ DB để chu kỳ luôn tăng dần liên tục, không bị reset về 0 khi khởi động lại."""
    try:
        st = database.get_all_bot_status(db_file=db_file).get("total_scans")
        if st and str(st).isdigit() and int(st) > 0:
            return int(st)
    except Exception:
        pass
    try:
        conn = database.get_connection(db_file)
        cur = conn.cursor()
        cur.execute("SELECT message FROM system_logs WHERE message LIKE '%Chu kỳ #%' ORDER BY id DESC LIMIT 20")
        rows = cur.fetchall()
        max_c = 0
        for r in rows:
            msg = r[0] if isinstance(r, (tuple, list)) else r["message"]
            m = re.search(r"Chu kỳ #(\d+)", msg)
            if m:
                c_num = int(m.group(1))
                if c_num > max_c:
                    max_c = c_num
        if max_c > 0:
            return max_c
    except Exception:
        pass
    return 0

def run_bot():'''
        code = code.replace("def run_bot():", get_c_func, 1)

    # 2. Update cycle = 0 -> cycle = get_initial_cycle(DB_TARGET)
    code = re.sub(r'cycle\s*=\s*0', 'cycle = get_initial_cycle(DB_TARGET)', code, count=1)

    # 3. Add SCAN log at start of cycle
    old_start = '''database.set_bot_status("bot_state", "scanning", db_file=DB_TARGET)'''
    new_start = '''database.set_bot_status("bot_state", "scanning", db_file=DB_TARGET)
        database.log_event("SCAN", f"🔄 Chu kỳ #{cycle}: Bắt đầu quét Cổng Hoạt động UFM...", db_file=DB_TARGET)'''
    if old_start in code and new_start not in code:
        code = code.replace(old_start, new_start, 1)

    # 4. Add completion SCAN log
    old_end = '''database.log_event("SCAN", f"🔄 Chu kỳ #{cycle}: Hoàn tất kiểm tra cổng ĐRL UFM ({len(activities)} hoạt động).", db_file=DB_TARGET)'''
    new_end = '''post_stat = f"{new_count} bài mới" if new_count > 0 else "0 bài mới"
                if reopened_count > 0:
                    post_stat += f", {reopened_count} mở slot"
                database.log_event("SCAN", f"✅ Chu kỳ #{cycle}: Hoàn tất kiểm tra Cổng UFM ({len(activities)} hoạt động, {post_stat}). Tạm nghỉ {interval}s trước chu kỳ #{cycle+1}.", db_file=DB_TARGET)'''
    if old_end in code:
        code = code.replace(old_end, new_end, 1)

    with open(p, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"Patched {p} successfully!")

patch_file(r"c:\Users\Admin\Documents\HUIT\ufm_bot.py")
patch_file(r"c:\Users\Admin\Documents\HUIT\vaa\ufm\bot.py")
