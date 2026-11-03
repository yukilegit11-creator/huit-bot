import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(r'c:\Users\Admin\Documents\HUIT\ufm_bot.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, l in enumerate(lines[:50]):
    if 'DB' in l:
        print(f"{i+1}: {l.strip()}")
