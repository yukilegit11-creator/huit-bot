import sqlite3
conn = sqlite3.connect('/root/huit-bot/ufm_bot.db')
cur = conn.cursor()
cur.execute('SELECT post_title, zalo_target_name, status, sent_at FROM delivery_history ORDER BY id DESC LIMIT 5')
for r in cur.fetchall():
    print(r)
conn.close()
