import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', 22, 'root', '2tLGYzo2Ihgl6wKX')

test_script = """import requests, ddddocr, urllib3, re, time
from bs4 import BeautifulSoup
urllib3.disable_warnings()

ocr = ddddocr.DdddOcr(show_ad=False)

def attempt_login(mssv, password, max_attempts=5):
    for att in range(1, max_attempts + 1):
        s = requests.Session()
        s.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Referer': 'https://doantn.iuh.edu.vn/login.html'
        })
        
        # 1. Get login page
        r_init = s.get('https://doantn.iuh.edu.vn/login.html', verify=False, timeout=10)
        
        # 2. Get captcha image
        r_cap = s.get('https://doantn.iuh.edu.vn/components/com_contact/captcha.php', verify=False, timeout=10)
        cap_raw = ocr.classification(r_cap.content)
        cap_code = re.sub(r'[^a-zA-Z0-9]', '', cap_raw).strip()
        print(f"Attempt #{att}: Raw OCR='{cap_raw}' -> Cleaned='{cap_code}'")
        
        if len(cap_code) != 5:
            print(f"  Captcha length is not 5 ({len(cap_code)}), skipping...")
            time.sleep(1)
            continue
            
        data = {
            'mssv': mssv,
            'password': password,
            'security_code': cap_code,
            'btLogin': 'Đăng nhập'
        }
        r_login = s.post('https://doantn.iuh.edu.vn/login.html', data=data, verify=False, timeout=10)
        
        # Check portal
        r_portal = s.get('https://doantn.iuh.edu.vn/doanvien.html', verify=False, timeout=10)
        if 'Phạm Thị Minh Hằng' in r_portal.text or 'KẾT QUẢ TRA CỨU' in r_portal.text or 'doanvien.html@profile' in r_portal.text:
            sess_id = s.cookies.get('PHPSESSID')
            print(f"🎉 LOGIN SUCCESS ON ATTEMPT #{att}!")
            print(f"🔑 New PHPSESSID: {sess_id}")
            return True, sess_id
        else:
            print(f"  Attempt #{att} failed: Not logged in")
            time.sleep(1)
            
    return False, None

success, sid = attempt_login('25640491', 'phamhang1207')
print('FINAL RESULT:', success, sid)
"""

sftp = ssh.open_sftp()
with sftp.file('/root/huit-bot/test_login_loop.py', 'w') as f:
    f.write(test_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /root/huit-bot/test_login_loop.py')
print('OUT:\n', stdout.read().decode('utf-8'))
print('ERR:\n', stderr.read().decode('utf-8'))
ssh.close()
