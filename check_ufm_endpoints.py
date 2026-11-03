import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/vaa/ufm/web_app.py", "r", encoding="utf-8") as f:
    text = f.read()

import re

# Find all button onclick handlers
onclicks = re.findall(r'onclick="([^"]+)"', text)
print(f"Total onclicks in ufm web_app: {len(onclicks)}")
for oc in sorted(set(onclicks)):
    print(f"onclick: {oc}")

# Find all fetch calls in functions
functions = re.findall(r'(async\s+)?function\s+([a-zA-Z0-9_]+)\s*\([^\)]*\)\s*\{([^}]+fetch[^}]+)\}', text)
print(f"\nFunctions with fetch: {len(functions)}")
for fn in functions:
    fn_name = fn[1]
    fn_body = fn[2]
    fetches = re.findall(r'fetch\(([^,\)]+)', fn_body)
    print(f"- {fn_name}: {fetches}")
