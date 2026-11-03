import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/web_app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if "HTMLResponse(" in line or "dashboard" in line.lower() and "def " in line:
        print(f"Line {idx+1}: {line.strip()[:100]}")
