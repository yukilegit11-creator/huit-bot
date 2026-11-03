
import sqlite3

for db_path in ['/root/huit-bot/ufm_bot.db', '/root/huit-bot/vaa/ufm/ufm_bot.db']:
    print(f"\n=== DB: {db_path} ===")
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("PRAGMA table_info(seen_activities)")
        print("cols:", [col[1] for col in c.fetchall()])
        c.execute("SELECT * FROM seen_activities LIMIT 5")
        for r in c.fetchall():
            print("  seen:", r)
        c.execute("SELECT * FROM crawled_activities ORDER BY id DESC LIMIT 5")
        for r in c.fetchall():
            print("  crawled:", r)
        conn.close()
    except Exception as e:
        print("Err:", e)
