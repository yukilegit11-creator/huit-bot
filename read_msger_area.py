import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open(r'c:\Users\Admin\Documents\HUIT\messenger_sender.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print('Lines count:', len(lines))
print(''.join(lines[180:240]))
