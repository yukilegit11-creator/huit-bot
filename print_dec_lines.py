import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/web_app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for lno in [1343, 2910, 4532]:
    start = max(0, lno - 5)
    end = min(len(lines), lno + 5)
    print(f"=== Around line {lno} ===")
    for j in range(start, end):
        print(f"{j+1}: {lines[j]}", end="")
