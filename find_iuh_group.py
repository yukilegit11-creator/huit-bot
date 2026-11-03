import sys
import json
import paramiko

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Fetch Zalo groups using the Zalo client on VPS
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', port=22, username='root', password='2tLGYzo2Ihgl6wKX', timeout=10)

cmd = '''python3 -c "
import sys, json
sys.path.insert(0, '/root/huit-bot')
from zalo_sender import ZaloDispatcher

disp = ZaloDispatcher('/root/huit-bot/config_iuh.json')
if disp.connect():
    groups = disp.fetch_all_groups()
    print('TOTAL GROUPS:', len(groups))
    for g in groups:
        name = g.get('name', '')
        gid = g.get('id', '')
        if any(k in name.lower() for k in ['iuh', 'rèn luyện', 'tb', 'drl', 'điểm']):
            print(f'MATCH: ID={gid} | NAME={name}')
        else:
            print(f'OTHER: ID={gid} | NAME={name}')
else:
    print('FAILED TO CONNECT ZALO')
"'''

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
ssh.close()
