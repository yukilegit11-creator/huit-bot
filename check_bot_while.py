import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(r'c:\Users\Admin\Documents\HUIT\bot.py', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('database.log_event("SYSTEM"')
print(text[idx:idx+1500])
