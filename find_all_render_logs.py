import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/web_app.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
funcs = re.findall(r'function\s+renderLogs\w*\s*\([^\)]*\)\s*\{[\s\S]*?\}', text)
print(f"Total renderLogs functions in root web_app.py: {len(funcs)}")
for i, fn in enumerate(funcs):
    print(f"--- Function {i+1} (len: {len(fn)}) ---")
    print(fn[:400])
