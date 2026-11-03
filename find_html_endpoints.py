import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/web_app.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
matches = re.findall(r'@app\.get\((["\'][^"\']+["\'])[^)]*\)\s*(?:async\s+)?def\s+([a-zA-Z0-9_]+)\([^)]*\)(?:[\s\S]*?HTMLResponse)', text)
for m in matches:
    print(f"Route: {m[0]} -> {m[1]}")
