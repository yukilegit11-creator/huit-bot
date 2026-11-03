import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

p = r'C:\Python314\Lib\site-packages\fbchat_muqit\utils\stateHelper.py'
with open(p, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(''.join(lines[30:80]))
