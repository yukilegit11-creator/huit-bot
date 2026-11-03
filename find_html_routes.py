import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/web_app.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
routes = re.findall(r'@app\.get\(["\']([^"\']+)["\']\)\s*(?:async\s+)?def\s+([a-zA-Z0-9_]+)', text)
for r in routes:
    if not r[0].startswith('/api') and not r[0].startswith('/health') and not r[0].startswith('/ping'):
        print(f"HTML Route: {r[0]} -> {r[1]}")
