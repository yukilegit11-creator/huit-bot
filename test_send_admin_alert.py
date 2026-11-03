import sys
import paramiko

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('180.93.125.40', port=22, username='root', password='2tLGYzo2Ihgl6wKX', timeout=10)

cmd = '''python3 -c "
import sys
sys.path.insert(0, '/root/huit-bot')
from zalo_sender import ZaloDispatcher
from zlapi.models import Message, ThreadType
from datetime import datetime, timezone, timedelta

disp = ZaloDispatcher('/root/huit-bot/config.json')
if disp.connect():
    ADMIN_UID = '7581087306337796515'
    now_vn = datetime.now(timezone(timedelta(hours=7))).strftime('%H:%M:%S %d/%m/%Y')
    warn_text = (
        '⚠️ [YUKI BOT - CẢNH BÁO COOKIE FACEBOOK HẾT HẠN] ⚠️\\n'
        '━━━━━━━━━━━━━━━━━━━━\\n'
        '🚨 Trạng thái: Phiên Cookie Facebook vừa bị đăng xuất hoặc hết hạn!\\n'
        '🌐 Hệ thống: Tự động kích hoạt Chế độ Ẩn danh (Guest Mode) để duy trì cào bài viết công khai.\\n'
        f'⏰ Thời gian: {now_vn}\\n'
        '━━━━━━━━━━━━━━━━━━━━\\n'
        '👉 Để tối ưu, bạn vui lòng truy cập Web Dashboard (mật khẩu YUKILEGIT0) để dán Cookie mới nhé!'
    )
    disp.client.send(Message(text=warn_text), thread_id=ADMIN_UID, thread_type=ThreadType.USER)
    print('SUCCESS: Sent warning alert to Admin Zalo!')
else:
    print('Failed to connect Zalo')
"'''

stdin, stdout, stderr = ssh.exec_command(cmd)
print(stdout.read().decode('utf-8', errors='replace'))
print(stderr.read().decode('utf-8', errors='replace'))
ssh.close()
