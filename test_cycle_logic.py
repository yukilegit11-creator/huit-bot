import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import sqlite3
import re
import database

def test_cycle():
    st = database.get_all_bot_status().get("scan_cycle")
    print("get_all_bot_status scan_cycle:", st)

    conn = database.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT message FROM system_logs WHERE message LIKE '%Chu kỳ #%' ORDER BY id DESC LIMIT 50")
    rows = cur.fetchall()
    max_c = 0
    for r in rows:
        msg = r[0] if isinstance(r, (tuple, list)) else r["message"]
        m = re.search(r"Chu kỳ #(\d+)", msg)
        if m:
            c_num = int(m.group(1))
            if c_num > max_c:
                max_c = c_num
    print("Max cycle found in system_logs:", max_c)

test_cycle()
