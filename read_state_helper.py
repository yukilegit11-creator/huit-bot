
with open('/usr/local/lib/python3.10/dist-packages/fbchat_muqit/utils/stateHelper.py', 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

for i, l in enumerate(lines):
    if 'async_get_token' in l or 'DTSG' in l or 'dtsg' in l.lower():
        start = max(0, i - 15)
        end = min(len(lines), i + 25)
        for j in range(start, end):
            print(f"{j+1}: {lines[j]}", end='')
        break
