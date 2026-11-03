import sys
import hashlib
import paramiko

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

files = [
    (r'c:\Users\Admin\Documents\HUIT\vaa\ufm\web_app.py', '/root/huit-bot/vaa/ufm/web_app.py'),
    (r'c:\Users\Admin\Documents\HUIT\vaa\ufm\templates\index.html', '/root/huit-bot/vaa/ufm/templates/index.html'),
    (r'c:\Users\Admin\Documents\HUIT\vaa\ufm\database.py', '/root/huit-bot/vaa/ufm/database.py'),
    (r'c:\Users\Admin\Documents\HUIT\zalo_sender.py', '/root/huit-bot/zalo_sender.py'),
    (r'c:\Users\Admin\Documents\HUIT\ufm_bot.py', '/root/huit-bot/ufm_bot.py')
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', port=22, username='root', password='2tLGYzo2Ihgl6wKX', timeout=10)

for local_path, vps_path in files:
    with open(local_path, 'rb') as f:
        local_hash = hashlib.md5(f.read()).hexdigest()
    stdin, stdout, stderr = ssh.exec_command(f'md5sum {vps_path}')
    res = stdout.read().decode('utf-8').strip()
    vps_hash = res.split()[0] if res else 'MISSING'
    print(f"{vps_path}: match={local_hash == vps_hash} (local={local_hash[:8]}, vps={vps_hash[:8]})")

ssh.close()
