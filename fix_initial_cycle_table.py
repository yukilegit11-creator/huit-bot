import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Fix bot.py
with open("c:/Users/Admin/Documents/HUIT/bot.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace('cur.execute("SELECT message FROM logs WHERE message LIKE', 'cur.execute("SELECT message FROM system_logs WHERE message LIKE')
text = text.replace('database.get_bot_status("scan_cycle", db_file=db_file)', 'database.get_all_bot_status(db_file=db_file).get("scan_cycle")')

with open("c:/Users/Admin/Documents/HUIT/bot.py", "w", encoding="utf-8") as f:
    f.write(text)

# Fix vaabot.py
with open("c:/Users/Admin/Documents/HUIT/vaabot.py", "r", encoding="utf-8") as f:
    text2 = f.read()

text2 = text2.replace('cur.execute("SELECT message FROM logs WHERE message LIKE', 'cur.execute("SELECT message FROM system_logs WHERE message LIKE')
text2 = text2.replace('database.get_bot_status("scan_cycle", db_file=db_file)', 'database.get_all_bot_status(db_file=db_file).get("scan_cycle")')

with open("c:/Users/Admin/Documents/HUIT/vaabot.py", "w", encoding="utf-8") as f:
    f.write(text2)

print("Fixed get_initial_cycle in bot.py and vaabot.py!")
