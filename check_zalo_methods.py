import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/vaa/ufm/zalo_sender.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
matches = [line for line in text.split("\n") if "def send_test" in line]
for m in matches:
    print(m)
