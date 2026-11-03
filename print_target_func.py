import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/vaa/ufm/web_app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for j in range(2160, 2200):
    print(f"{j+1}: {lines[j]}", end="")
