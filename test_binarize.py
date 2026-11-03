import paramiko, sys
sys.stdout.reconfigure(encoding='utf-8')
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', 22, 'root', '2tLGYzo2Ihgl6wKX')

test_script = """import io, ddddocr, re
from PIL import Image

ocr = ddddocr.DdddOcr(show_ad=False)

def solve_captcha(img_bytes):
    # Try raw first
    raw = ocr.classification(img_bytes)
    code = re.sub(r'[^a-zA-Z0-9]', '', raw).strip()
    if len(code) == 5:
        return code
        
    # Try binarized
    img = Image.open(io.BytesIO(img_bytes)).convert('L')
    bw = img.point(lambda p: 255 if p > 90 else 0)
    buf = io.BytesIO()
    bw.save(buf, format='PNG')
    raw_bw = ocr.classification(buf.getvalue())
    code_bw = re.sub(r'[^a-zA-Z0-9]', '', raw_bw).strip()
    if len(code_bw) == 5:
        return code_bw
        
    return code or code_bw

with open('/root/huit-bot/sample_cap1.png', 'rb') as f:
    b1 = f.read()
with open('/root/huit-bot/last_cap.png', 'rb') as f:
    b2 = f.read()

print('sample1 (aa845):', solve_captcha(b1))
print('sample2 (f3d62):', solve_captcha(b2))
"""

sftp = ssh.open_sftp()
with sftp.file('/root/huit-bot/test_ocr_bin.py', 'w') as f:
    f.write(test_script)
sftp.close()

stdin, stdout, stderr = ssh.exec_command('python3 /root/huit-bot/test_ocr_bin.py')
print('OUT:\n', stdout.read().decode('utf-8'))
print('ERR:\n', stderr.read().decode('utf-8'))
ssh.close()
