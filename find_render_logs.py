import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/web_app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if "renderLogs" in line or "fetchLogs" in line or "logContainer" in line or "log-container" in line:
        start = max(0, idx - 10)
        end = min(len(lines), idx + 40)
        print(f"=== Found at line {idx+1} ===")
        for j in range(start, end):
            print(f"{j+1}: {lines[j]}", end="")
        break
