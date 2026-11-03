import paramiko
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', port=22, username='root', password='2tLGYzo2Ihgl6wKX')

sftp = ssh.open_sftp()
code = """
from bs4 import BeautifulSoup
from collections import Counter

with open('/tmp/fb_resp.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')
scripts = soup.find_all('script')
types = Counter([s.get('type') for s in scripts])
print('Script types:', types)

# Search entire HTML for post texts or any page post
import re
print('Has \"comet_sections\":', 'comet_sections' in html)
print('Has \"message\":', 'message' in html)
print('Has \"post_id\":', 'post_id' in html)
print('Has \"story\":', 'story' in html)
print('Has \"creation_time\":', 'creation_time' in html)
print('Has \"publish_time\":', 'publish_time' in html)
print('Has \"feedback\":', 'feedback' in html)
"""

with sftp.file('/tmp/check_script_types.py', 'w') as f:
    f.write(code)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /tmp/check_script_types.py')
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
ssh.close()
