import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

p = r'C:\Python314\Lib\site-packages\fbchat_muqit\utils\stateHelper.py'
with open(p, 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('return (')
if idx != -1:
    print(text[idx:idx+500])
else:
    print("return ( not found")
