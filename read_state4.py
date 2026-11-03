
with open('/usr/local/lib/python3.10/dist-packages/fbchat_muqit/utils/stateHelper.py', 'r') as f:
    lines = f.readlines()

for i in range(195, 260):
    print(f"{i+1}: {lines[i]}", end='')
