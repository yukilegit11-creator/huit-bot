import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/web_app.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
matches = [line for line in text.split("\n") if "bot1-sort-text" in line or "bot1LogSort" in line or "toggleLogSort" in line]
for m in matches:
    print(m)
