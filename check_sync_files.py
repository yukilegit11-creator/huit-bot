import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/sync_to_vps.py", "r", encoding="utf-8") as f:
    text = f.read()

print("Contains index.html:", "index.html" in text)
print("Contains templates:", "templates" in text)
