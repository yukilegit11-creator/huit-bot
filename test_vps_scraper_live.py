import sys
import paramiko

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', port=22, username='root', password='2tLGYzo2Ihgl6wKX', timeout=10)

cmd = '''python3 -c "
import sys, json
sys.path.insert(0, '/root/huit-bot')
from scraper import FacebookCometScraper

cfg = json.load(open('/root/huit-bot/config.json'))
cookies = cfg.get('fb_cookies', {})
print('Testing scraper on VPS with c_user:', cookies.get('c_user'))
scraper = FacebookCometScraper(cookies)
html = scraper.fetch_url('https://www.facebook.com/HUITFIT')
print('Fetched HTML length:', len(html) if html else 0)
posts = scraper.parse_posts(html, page_url='https://www.facebook.com/HUITFIT')
print('Parsed posts count:', len(posts))
"'''

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
ssh.close()
