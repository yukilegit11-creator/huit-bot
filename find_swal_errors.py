import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/vaa/ufm/web_app.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
# Find all occurrences of Swal.fire('Lỗi', ... or Swal.fire({ title: 'Lỗi' ...
matches = re.findall(r"Swal\.fire\(\s*['\"]Lỗi['\"],\s*([^,\)]+)", text)
for m in matches:
    print("Match:", m)
