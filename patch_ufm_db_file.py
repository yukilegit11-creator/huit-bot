import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/vaa/ufm/database.py", "r", encoding="utf-8") as f:
    text = f.read()

if "UFM_DB_FILE = DB_FILE" not in text:
    text = text.replace("DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), \"ufm_bot.db\")", "DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), \"ufm_bot.db\")\nUFM_DB_FILE = DB_FILE")
    with open("c:/Users/Admin/Documents/HUIT/vaa/ufm/database.py", "w", encoding="utf-8") as f:
        f.write(text)
    print("Added UFM_DB_FILE = DB_FILE to vaa/ufm/database.py!")
else:
    print("Already exists in vaa/ufm/database.py!")
