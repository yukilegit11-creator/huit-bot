import threading
import time
import subprocess
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def run_proc(cmd, name):
    print(f"🚀 [Khởi động {name}]...")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(
        [sys.executable, cmd],
        cwd=SCRIPT_DIR,
        env=env
    )
    proc.wait()

def main():
    print("=" * 60)
    print("🌟 HỆ THỐNG ĐIỀU HÀNH DUAL BOT (BOT 1 HUIT & BOT 2 RIÊNG BIỆT)")
    print("=" * 60)

    t1 = threading.Thread(target=run_proc, args=("bot.py", "Bot 1 (HUIT)"), daemon=True)
    t2 = threading.Thread(target=run_proc, args=("bot2.py", "Bot 2 (Kênh Riêng)"), daemon=True)

    t1.start()
    time.sleep(2)
    t2.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Dừng toàn bộ hệ thống Dual Bot.")

if __name__ == "__main__":
    main()
