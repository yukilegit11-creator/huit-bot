import sys
import paramiko

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', port=22, username='root', password='2tLGYzo2Ihgl6wKX', timeout=10)

stdin, stdout, stderr = ssh.exec_command('python3 -c "import sys; sys.path.insert(0, \'/root/huit-bot\'); import database; logs = database.get_recent_logs(limit=10, db_file=database.UFM_DB_FILE); [print(l[\'timestamp\'] + \' | \' + l[\'event_type\'] + \' | \' + l[\'message\']) for l in logs]"')
print(stdout.read().decode('utf-8', errors='replace'))
ssh.close()
