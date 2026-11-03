import sqlite3
conn = sqlite3.connect('/root/huit-bot/ufm_bot.db')
c = conn.cursor()
c.execute("SELECT post_id, post_title, zalo_target_name, status, sent_at FROM delivery_history ORDER BY id DESC LIMIT 15")
rows = c.fetchall()
print(f"Total recent deliveries found: {len(rows)}")
for r in rows:
    print(" ", r)
conn.close()
