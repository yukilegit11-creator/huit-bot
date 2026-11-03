import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/database.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if "def get_bot_status" in line:
        for j in range(idx, min(len(lines), idx + 25)):
            print(f"{j+1}: {lines[j]}", end="")
        break
