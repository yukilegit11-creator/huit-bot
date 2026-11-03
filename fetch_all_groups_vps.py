import sys
import paramiko

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', port=22, username='root', password='2tLGYzo2Ihgl6wKX', timeout=10)

cmd = '''python3 -c "
import sys, json
sys.path.insert(0, '/root/huit-bot')
from zalo_sender import ZaloDispatcher

disp = ZaloDispatcher('/root/huit-bot/config_iuh.json')
if disp.connect():
    groups = disp.get_groups()
    print('TOTAL:', len(groups))
    for g in groups:
        gid = g.get('id', '')
        gname = g.get('name', '')
        print(json.dumps({'id': gid, 'name': gname}, ensure_ascii=False))
"'''

stdin, stdout, stderr = ssh.exec_command(cmd)
lines = stdout.read().decode('utf-8', errors='replace').splitlines()
for l in lines:
    if any(k in l.lower() for k in ['iuh', 'rèn luyện', 'tb', 'drl', 'điểm', 'thông báo']):
        print(l)
ssh.close()
