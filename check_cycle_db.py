import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import sqlite3

conn = sqlite3.connect("c:/Users/Admin/Documents/HUIT/huit_bot.db")
cur = conn.cursor()
cur.execute("SELECT id, created_at, message FROM logs WHERE message LIKE '%Chu kỳ #%' ORDER BY id DESC LIMIT 15")
rows = cur.fetchall()
print("Recent cycle logs in local huit_bot.db:")
for r in rows:
    print(r)
