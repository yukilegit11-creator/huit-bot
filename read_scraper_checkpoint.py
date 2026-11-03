import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(r'c:\Users\Admin\Documents\HUIT\scraper.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, l in enumerate(lines):
    if 'Checkpoint' in l or 'Guest Mode' in l:
        print(f"{i+1}: {l.strip()}")
        print(''.join(lines[max(0, i-15):min(len(lines), i+15)]))
