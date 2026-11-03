import sqlite3

db_path = '/root/huit-bot/iuh_bot.db'
print("=== Checking:", db_path)
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Check seen_activities
try:
    c.execute("SELECT activity_id, title, status, slots, is_sent, first_seen, last_updated FROM seen_activities WHERE activity_id LIKE '%4286%'")
    rows = c.fetchall()
    print("seen_activities 4286:", rows)
except Exception as e:
    print("seen_activities err:", e)

# Check all in seen_activities
try:
    c.execute("SELECT activity_id, title, status, slots, is_sent FROM seen_activities")
    print("ALL seen_activities:")
    for r in c.fetchall():
        print(" ", r)
except Exception as e:
    print("err:", e)

# Check delivery_history
try:
    c.execute("SELECT post_id, post_title, zalo_target_name, status, sent_at FROM delivery_history WHERE post_id LIKE '%4286%'")
    rows = c.fetchall()
    print("delivery_history 4286:", rows)
except Exception as e:
    print("delivery_history err:", e)

# Check system_logs for 4286 or recent logs
try:
    c.execute("SELECT level, message, created_at FROM system_logs ORDER BY id DESC LIMIT 20")
    print("Recent IUH logs:")
    for r in c.fetchall():
        print(" ", r)
except Exception as e:
    print("system_logs err:", e)

conn.close()
