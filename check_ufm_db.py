
import sqlite3

conn = sqlite3.connect('/root/huit-bot/ufm_bot.db')
c = conn.cursor()

print("=== Checking new IDs in seen_activities ===")
for test_id in ['16586', '16585', '16589', '16597', '16454']:
    c.execute("SELECT activity_id, title, crawled_at FROM seen_activities WHERE activity_id = ?", (test_id,))
    row = c.fetchone()
    print(f"ID {test_id} in seen_activities: {row}")

print("\n=== Checking latest crawled_activities ===")
c.execute("SELECT activity_id, title, status, points, crawled_at, is_sent_zalo FROM crawled_activities ORDER BY id DESC LIMIT 10")
for r in c.fetchall():
    print(" ", r)

print("\n=== Checking recent system_logs for UFM ===")
c.execute("SELECT level, message, created_at FROM system_logs ORDER BY id DESC LIMIT 15")
for r in c.fetchall():
    print(f"  [{r[2]}] [{r[0]}] {r[1]}")

conn.close()
