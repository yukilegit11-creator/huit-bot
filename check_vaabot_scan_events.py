import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(r'c:\Users\Admin\Documents\HUIT\vaabot.py', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('database.log_event("SCAN"')
if idx != -1:
    print(text[idx:idx+800])
else:
    print("vaabot.py has NO database.log_event SCAN!")
