import re
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(r'c:\Users\Admin\Documents\HUIT\vaa\ufm\templates\index.html', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('Bot 4: UFM')
print(text[max(0, idx-150):min(len(text), idx+300)])
