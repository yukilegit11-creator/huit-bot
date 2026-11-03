import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(r'c:\Users\Admin\Documents\HUIT\ufm_bot.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(''.join(lines[360:415]))
