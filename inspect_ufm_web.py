import re

with open("c:/Users/Admin/Documents/HUIT/vaa/ufm/web_app.py", "r", encoding="utf-8") as f:
    text = f.read()

matches = re.findall(r"fetch\((['\"`][^'\"`\)]+['\"`])", text)
print("Fetch calls in vaa/ufm/web_app.py:")
for m in sorted(set(matches)):
    print(m)

# Also find all routes defined in web_app.py
routes = re.findall(r"@app\.(get|post|put|delete)\((['\"][^'\"]+['\"])", text)
print("\nRoutes defined in vaa/ufm/web_app.py:")
for r in sorted(set(routes)):
    print(f"{r[0].upper()} {r[1]}")
