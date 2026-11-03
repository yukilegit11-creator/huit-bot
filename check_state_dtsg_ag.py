import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

p = r'C:\Python314\Lib\site-packages\fbchat_muqit\utils\stateHelper.py'
with open(p, 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('fb_dtsg_ag')
while idx != -1:
    print(text[max(0, idx-50):min(len(text), idx+150)])
    print('---')
    idx = text.find('fb_dtsg_ag', idx+1)
