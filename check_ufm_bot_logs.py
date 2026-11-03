import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(r'c:\Users\Admin\Documents\HUIT\ufm_bot.py', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('database.log_event')
while idx != -1:
    print(text[idx:idx+120])
    print('---')
    idx = text.find('database.log_event', idx+1)
