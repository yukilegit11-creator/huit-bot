import sys, sqlite3
sys.path.insert(0, '/root/huit-bot')
from messenger_sender import MessengerDispatcher

conn = sqlite3.connect('/root/huit-bot/huit_bot.db')
cur = conn.cursor()
cur.execute('SELECT post_id, page_name, author, content, post_url, posted_time FROM crawled_posts WHERE page_name LIKE "%HUIT%" OR content LIKE "%HUIT%" ORDER BY id DESC LIMIT 1')
row = cur.fetchone()

if not row:
    print('No post found in DB!')
    sys.exit(0)

post = {
    'post_id': row[0],
    'page_name': row[1],
    'author': row[2],
    'content': row[3],
    'post_url': row[4],
    'posted_time': row[5]
}
page_name = row[1]
print('Found HUIT post:')
print('Page:', page_name)
print('Title/Snippet:', post['content'][:120].replace('\n', ' '))
print('URL:', post['post_url'])

dispatcher = MessengerDispatcher('/root/huit-bot/config.json', db_file='/root/huit-bot/huit_bot.db')
print('Connecting to Messenger...')
if dispatcher.connect():
    print('Connected as:', dispatcher.client.uid if dispatcher.client else 'OK')
    print('Sending alert to target groups...')
    res = dispatcher.send_post_alert(post, page_name, matched_kw='ĐRL / Kỹ năng sinh viên HUIT')
    print('send_post_alert result:', res)
else:
    print('Failed to connect to Messenger!')
