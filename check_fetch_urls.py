import re

with open(r'c:\Users\Admin\Documents\HUIT\vaa\ufm\templates\index.html', 'r', encoding='utf-8') as f:
    html = f.read()

fetches = re.findall(r'fetch\([\'"]([^\'"]+)[\'"]', html)
print(f"Total fetch calls: {len(fetches)}")
for u in sorted(set(fetches)):
    print("  ->", u)
