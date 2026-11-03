import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(r'c:\Users\Admin\Documents\HUIT\ufm_bot.py', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('def run_ufm_bot')
print(text[idx:idx+2500])
