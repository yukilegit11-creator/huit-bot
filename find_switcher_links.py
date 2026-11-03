import re
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(r'c:\Users\Admin\Documents\HUIT\web_app.py', 'r', encoding='utf-8') as f:
    text = f.read()

matches = [m.start() for m in re.finditer(r'href=["\']/ufm["\']', text)]
print("Total switcher links found in web_app.py:", len(matches))
for idx in matches:
    print("--- MATCH AT", idx)
    print(text[max(0, idx-50):min(len(text), idx+250)])
