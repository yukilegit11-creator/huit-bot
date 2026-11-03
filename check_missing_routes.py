import re
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(r'c:\Users\Admin\Documents\HUIT\vaa\ufm\templates\index.html', 'r', encoding='utf-8') as f:
    html = f.read()

fetches = sorted(set(re.findall(r'fetch\([\'"]([^\'"]+)[\'"]', html)))

with open(r'c:\Users\Admin\Documents\HUIT\vaa\ufm\web_app.py', 'r', encoding='utf-8') as f:
    py_code = f.read()

routes = set(re.findall(r'@app\.(?:get|post|delete|put)\([\'"]([^\'"]+)[\'"]', py_code))

print("=== CHECKING FETCH URLS IN UFM WEB_APP.PY ===")
for u in fetches:
    clean_u = u.split('?')[0]
    matched = clean_u in routes
    status = "OK" if matched else "MISSING"
    print(f"[{status}] {clean_u}")
