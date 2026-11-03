import os
import sys
import time
import paramiko

sys.stdout.reconfigure(encoding='utf-8')

ROOT_DIR = r"C:\Users\Admin\Documents\HUIT"
HOST = "180.93.125.40"
PORT = 22
USER = "root"
PASS = "2tLGYzo2Ihgl6wKX"

files_to_sync = [
    ("bot.py", "/root/huit-bot/bot.py"),
    ("vaabot.py", "/root/huit-bot/vaabot.py"),
    ("iuh_bot.py", "/root/huit-bot/iuh_bot.py"),
    ("ufm_bot.py", "/root/huit-bot/ufm_bot.py"),
    ("database.py", "/root/huit-bot/database.py"),
    ("web_app.py", "/root/huit-bot/web_app.py"),
    ("zalo_sender.py", "/root/huit-bot/zalo_sender.py"),
    ("messenger_sender.py", "/root/huit-bot/messenger_sender.py"),
    ("iuh_scraper.py", "/root/huit-bot/iuh_scraper.py"),
    ("ufm_scraper.py", "/root/huit-bot/ufm_scraper.py"),
    ("fb_cookies.json", "/root/huit-bot/fb_cookies.json"),
    ("config.json", "/root/huit-bot/config.json"),
    ("config_bot2.json", "/root/huit-bot/config_bot2.json"),
    ("config_iuh.json", "/root/huit-bot/config_iuh.json"),
    ("config_ufm.json", "/root/huit-bot/config_ufm.json"),
    ("vaabot.json", "/root/huit-bot/vaabot.json"),
    ("vaa/config.json", "/root/huit-bot/vaa/config.json"),
    ("vaa/vaabot.json", "/root/huit-bot/vaa/vaabot.json"),
    ("vaa/web_app.py", "/root/huit-bot/vaa/web_app.py"),
    ("vaa/zalo_sender.py", "/root/huit-bot/vaa/zalo_sender.py"),
    ("vaa/ufm/bot.py", "/root/huit-bot/vaa/ufm/bot.py"),
    ("vaa/ufm/ufm_scraper.py", "/root/huit-bot/vaa/ufm/ufm_scraper.py"),
    ("vaa/ufm/database.py", "/root/huit-bot/vaa/ufm/database.py"),
    ("vaa/ufm/web_app.py", "/root/huit-bot/vaa/ufm/web_app.py"),
    ("vaa/ufm/zalo_sender.py", "/root/huit-bot/vaa/ufm/zalo_sender.py"),
    ("vaa/ufm/config.json", "/root/huit-bot/vaa/ufm/config.json"),
    ("vaa/ufm/fb_cookies.json", "/root/huit-bot/vaa/ufm/fb_cookies.json"),
]

print("Connecting to VPS via SSH/SFTP...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, PORT, USER, PASS, timeout=15)
sftp = ssh.open_sftp()

print("Uploading files to VPS /root/huit-bot/...")
for local_rel, remote_abs in files_to_sync:
    local_abs = os.path.join(ROOT_DIR, local_rel.replace("/", os.sep))
    if os.path.exists(local_abs):
        # Ensure remote dir exists
        remote_dir = os.path.dirname(remote_abs)
        ssh.exec_command(f"mkdir -p {remote_dir}")
        sftp.put(local_abs, remote_abs)
        print(f"  -> Uploaded: {local_rel} => {remote_abs}")
    else:
        print(f"  ⚠️ Warning: Local file not found: {local_abs}")

sftp.close()

print("\nVerifying python compilation on VPS...")
stdin, stdout, stderr = ssh.exec_command("python3 -m py_compile /root/huit-bot/bot.py /root/huit-bot/vaabot.py /root/huit-bot/iuh_bot.py /root/huit-bot/ufm_bot.py /root/huit-bot/iuh_scraper.py /root/huit-bot/ufm_scraper.py /root/huit-bot/database.py /root/huit-bot/web_app.py /root/huit-bot/zalo_sender.py /root/huit-bot/messenger_sender.py /root/huit-bot/vaa/ufm/bot.py /root/huit-bot/vaa/ufm/web_app.py")
compile_err = stderr.read().decode('utf-8', errors='ignore')
if compile_err:
    print(f"❌ VPS Compilation Error:\n{compile_err}")
    ssh.close()
    sys.exit(1)
print("✅ Python files compiled cleanly on VPS!")

print("\nRestarting systemd service huit-bot...")
ssh.exec_command("systemctl restart huit-bot")
time.sleep(3)

print("Checking service status...")
stdin, stdout, stderr = ssh.exec_command("systemctl is-active huit-bot")
status = stdout.read().decode('utf-8').strip()
print(f"huit-bot service is: {status}")

print("Testing local API health on VPS...")
stdin, stdout, stderr = ssh.exec_command("curl -s http://127.0.0.1:8000/health")
health_res = stdout.read().decode('utf-8', errors='ignore')
print(f"Health response: {health_res}")

ssh.close()
print("All files synced and service restarted successfully!")
