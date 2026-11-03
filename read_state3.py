
with open('/usr/local/lib/python3.10/dist-packages/fbchat_muqit/state.py', 'r') as f:
    lines = f.readlines()

for i in range(330, 368):
    print(f"{i+1}: {lines[i]}", end='')
