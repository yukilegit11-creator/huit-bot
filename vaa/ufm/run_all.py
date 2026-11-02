import subprocess
import sys
import os
import time

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

print("=" * 65)
print("🚀 [YUKI 4 - UFM BOT] KHỞI CHẠY TẤT CẢ DỊCH VỤ")
print("🎓 Đơn vị: Trường Đại học Tài chính - Marketing (UFM)")
print("👤 Quản trị viên: Trần Lê Phát (@yukilegit11-creator)")
print("🌐 Web Dashboard: http://localhost:5004")
print("=" * 65)

procs = []

try:
    print("🌐 Khởi động Web Dashboard UFM (Port 5004)...")
    p_web = subprocess.Popen([sys.executable, "-u", os.path.join(SCRIPT_DIR, "web_app.py")])
    procs.append(p_web)

    time.sleep(2)

    print("🤖 Khởi động Bot UFM quét tự động 24/7...")
    p_bot = subprocess.Popen([sys.executable, "-u", os.path.join(SCRIPT_DIR, "bot.py")])
    procs.append(p_bot)

    print("✅ Cả 2 dịch vụ UFM đang chạy nền.")
    for p in procs:
        p.wait()

except KeyboardInterrupt:
    print("\n🛑 Nhận lệnh dừng hệ thống UFM...")
    for p in procs:
        try:
            p.terminate()
        except Exception:
            pass
    print("👋 Đã dừng an toàn tất cả các tiến trình UFM.")
