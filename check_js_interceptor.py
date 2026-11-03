import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/vaa/ufm/web_app.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
scripts = re.findall(r"<script[\s\S]*?</script>", text)
print(f"Total script tags: {len(scripts)}")
for i, s in enumerate(scripts):
    if "fetch" in s:
        print(f"\n--- Script {i} (len: {len(s)}) ---")
        lines = s.split("\n")
        print("\n".join(lines[:35]))
