import os
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

keywords = ["Yuki", "7581087306337796515", "845005453098855468"]

for root, dirs, files in os.walk(r'c:\Users\Admin\Documents\HUIT'):
    if any(x in root for x in ['.git', '__pycache__', 'node_modules']):
        continue
    for f in files:
        if f.endswith(('.py', '.json', '.html', '.md')):
            p = os.path.join(root, f)
            try:
                with open(p, 'r', encoding='utf-8', errors='ignore') as fl:
                    content = fl.read()
                    matches = [kw for kw in keywords if kw in content]
                    if matches:
                        print(f"{p}: found {matches}")
            except Exception:
                pass
