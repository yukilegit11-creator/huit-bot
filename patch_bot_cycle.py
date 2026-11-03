import os
import re

bot_py_path = "c:/Users/Admin/Documents/HUIT/bot.py"
with open(bot_py_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add get_initial_cycle helper function
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

# 2. In run_bot(), replace cycle = 0 with cycle = get_initial_cycle()
content = content.replace("    cycle = 0\n    total_new_posts = 0", "    cycle = get_initial_cycle()\n    total_new_posts = 0")

with open(bot_py_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated get_initial_cycle in bot.py!")
