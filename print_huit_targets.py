import json
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(r'c:\Users\Admin\Documents\HUIT\config.json', 'r', encoding='utf-8') as f:
    cfg = json.load(f)

targets = cfg.get('targets', [])
print(f'Total targets in config.json: {len(targets)}')
for i, t in enumerate(targets):
    print(f"{i+1}: {t.get('name')} -> {t.get('url')}")
