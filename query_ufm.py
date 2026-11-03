import sqlite3

conn = sqlite3.connect('/root/huit-bot/ufm_bot.db')
cur = conn.cursor()

print('=== RECENT SYSTEM LOGS ===')
logs = cur.execute('SELECT level, message, created_at FROM system_logs ORDER BY id DESC LIMIT 25').fetchall()
for l in logs:
    print(f'[{l[2]}] [{l[0]}] {l[1]}')

print('\n=== SEEN ACTIVITIES ===')
acts = cur.execute('SELECT activity_id, title, status, slots, is_sent, first_seen FROM seen_activities ORDER BY first_seen DESC LIMIT 15').fetchall()
for a in acts:
    print(a)

print('\n=== BOT STATUS ===')
st = cur.execute('SELECT key, value, updated_at FROM bot_status').fetchall()
for s in st:
    print(s)

conn.close()
