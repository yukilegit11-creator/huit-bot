import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', 22, 'root', '2tLGYzo2Ihgl6wKX')
sftp = ssh.open_sftp()
sftp.put(r'c:\Users\Admin\Documents\HUIT\sample_cap1.png', '/root/huit-bot/sample_cap1.png')
sftp.close()

script = """
import ddddocr
ocr = ddddocr.DdddOcr(show_ad=False)
with open('/root/huit-bot/sample_cap1.png', 'rb') as f:
    res = ocr.classification(f.read())
print('OCR_RESULT:', res)
"""
stdin, stdout, stderr = ssh.exec_command(f"python3 -c \"{script}\"")
print(stdout.read().decode('utf-8'))
print(stderr.read().decode('utf-8'))
ssh.close()
