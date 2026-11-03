import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(r'c:\Users\Admin\Documents\HUIT\bot.py', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('for i, target in enumerate(targets, 1):')
print(text[idx:idx+2000])
