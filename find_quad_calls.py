import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/vaa/ufm/web_app.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
matches = [line for line in text.split("\n") if "Test Nhóm Zalo" in line or "Gửi nhóm demo" in line or "openQuadTestModal" in line or "send-demo-alert" in line]
for m in matches:
    print(m)
