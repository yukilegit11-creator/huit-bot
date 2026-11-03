import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/vaa/ufm/web_app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if "DOCTYPE" in line or "@app.get(\"/\")" in line or "dashboard" in line.lower() and "def " in line:
        print(f"Line {idx+1}: {line.strip()[:100]}")
