import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/web_app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

print("--- BOT 3 STATS CARDS & TABS (lines 4630-4750) ---")
for j in range(4630, 4750):
    print(f"{j+1}: {lines[j]}", end="")
