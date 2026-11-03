import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

p = r'C:\Python314\Lib\site-packages\fbchat_muqit\utils\stateHelper.py'
with open(p, 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('async_get_token')
print(text[max(0, idx-300):min(len(text), idx+500)])
