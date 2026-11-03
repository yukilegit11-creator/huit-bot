
import sqlite3
conn = sqlite3.connect('/root/huit-bot/huit_bot.db')
cur = conn.cursor()
cur.execute('SELECT post_id, page_name, author, content, post_url, posted_time FROM crawled_posts ORDER BY id DESC LIMIT 5')
rows = cur.fetchall()
print(f'Total rows fetched: {len(rows)}')
for r in rows:
    print('---')
    print('Page:', r[1])
    print('Author:', r[2])
    print('URL:', r[4])
    print('Time:', r[5])
    print('Content:', r[3][:200].replace('\n', ' '))
