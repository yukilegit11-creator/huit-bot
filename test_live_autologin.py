import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', 22, 'root', '2tLGYzo2Ihgl6wKX')

test_script = """import sys
sys.path.insert(0, '/root/huit-bot')
from iuh_scraper import IUHPortalScraper

# Initialize scraper with NO session, but with student credentials
scraper = IUHPortalScraper(
    cookie_raw='',
    username='25640491',
    password='11022007',
    config_path='/root/huit-bot/config_iuh.json',
    auto_relogin=True
)

print('Testing fetch_activities with auto-login on VPS...')
ok, msg, acts = scraper.fetch_activities()
print('Result OK:', ok)
print('Message:', msg)
print('Activities fetched:', len(acts))
print('New PHPSESSID obtained:', scraper.phpsessid)
"""

sftp = ssh.open_sftp()
with sftp.file('/root/huit-bot/test_live_autologin.py', 'w') as f:
    f.write(test_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /root/huit-bot/test_live_autologin.py')
print('OUT:\n', stdout.read().decode('utf-8'))
print('ERR:\n', stderr.read().decode('utf-8'))
ssh.close()
