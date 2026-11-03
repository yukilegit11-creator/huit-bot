import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', 22, 'root', '2tLGYzo2Ihgl6wKX', timeout=10)

patch_script = """
fp = '/usr/local/lib/python3.10/dist-packages/fbchat_muqit/utils/stateHelper.py'
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

target = '''    fb_dtsg_ag = re.search(pattern, html)
    if fb_dtsg_ag:
        fb_dtsg_ag = fb_dtsg_ag.group(1)
    else:
        raise ValidationError("'async_get_token' not found.")'''

replacement = '''    fb_dtsg_ag = re.search(pattern, html)
    if fb_dtsg_ag:
        fb_dtsg_ag = fb_dtsg_ag.group(1)
    else:
        # Fallback to fb_dtsg for modern Facebook SSR
        fb_dtsg_ag = fb_dtsg'''

if target in content:
    content = content.replace(target, replacement)
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(content)
    print('SUCCESSFULLY PATCHED stateHelper.py!')
else:
    print('Target pattern not found or already patched.')
"""

sftp = ssh.open_sftp()
with sftp.file('/root/huit-bot/patch_state_helper.py', 'w') as f:
    f.write(patch_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /root/huit-bot/patch_state_helper.py')
print("STDOUT:\n", stdout.read().decode('utf-8', errors='ignore'))
print("STDERR:\n", stderr.read().decode('utf-8', errors='ignore'))
ssh.close()
