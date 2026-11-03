import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/sync_to_vps.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for j in range(15, 65):
    if j < len(lines):
        print(f"{j+1}: {lines[j]}", end="")
