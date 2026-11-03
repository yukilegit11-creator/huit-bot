import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/bot.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if "def run_bot" in line or "while True:" in line or "cycle" in line:
        start = max(0, idx - 5)
        end = min(len(lines), idx + 70)
        print(f"=== Found at line {idx+1} ===")
        for j in range(start, end):
            print(f"{j+1}: {lines[j]}", end="")
        break
