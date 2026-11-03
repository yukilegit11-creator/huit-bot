import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/vaa/ufm/web_app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if "send-demo-alert" in line or "Gửi nhóm demo" in line:
        start = max(0, idx - 15)
        end = min(len(lines), idx + 25)
        print(f"=== Line {idx+1} ===")
        for j in range(start, end):
            print(f"{j+1}: {lines[j]}", end="")
