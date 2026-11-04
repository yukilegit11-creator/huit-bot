import threading
import time
import subprocess
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def run_proc(cmd, name):
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    while True:
        print(f"🚀 [Khởi động {name}]...")
        try:
            proc = subprocess.Popen(
                [sys.executable, "-u", cmd],
                cwd=SCRIPT_DIR,
                env=env
            )
            ret = proc.wait()
            print(f"⚠️ [{name}] đã dừng (mã thoát: {ret}). Tự động khởi động lại sau 5 giây...")
        except Exception as e:
            print(f"❌ Lỗi tiến trình [{name}]: {e}")
        time.sleep(5)

def run_telegram():
    try:
        from telegram_bot import get_telegram_bot
        tg_bot = get_telegram_bot()
        while not tg_bot.is_configured():
            time.sleep(15)
            
        print("📱 [Khởi động Telegram Controller]...")
        tg_bot.broadcast_admin("🚀 <b>Hệ thống Penta-Bot đã khởi động và sẵn sàng nhận lệnh!</b>")
        tg_bot.poll_updates()
    except Exception as e:
        print(f"⚠️ Lỗi tiến trình Telegram Controller: {e}")

def main():
    print("=" * 60)
    print("🌟 HỆ THỐNG ĐIỀU HÀNH PENTA-BOT 24/7 (HUIT + VAA + IUH + UFM + OU ĐRL)")
    print("=" * 60)

    t1 = threading.Thread(target=run_proc, args=("bot.py", "Bot 1 (HUIT - Yuki 1)"), daemon=True)
    bot2_script = "vaabot.py" if os.path.exists(os.path.join(SCRIPT_DIR, "vaabot.py")) else "bot2.py"
    t2 = threading.Thread(target=run_proc, args=(bot2_script, "Bot 2 (VAA - Yuki 2)"), daemon=True)
    t3 = threading.Thread(target=run_proc, args=("iuh_bot.py", "Bot 3 (IUH - Yuki 3 ĐRL)"), daemon=True)
    t4 = threading.Thread(target=run_proc, args=("ufm_bot.py", "Bot 4 (UFM - Yuki 4 ĐRL)"), daemon=True)
    t5 = threading.Thread(target=run_proc, args=("ou_bot.py", "Bot 5 (OU - Yuki 5 ĐRL)"), daemon=True)
    t_tg = threading.Thread(target=run_telegram, daemon=True)

    t1.start()
    time.sleep(2)
    t2.start()
    time.sleep(2)
    t3.start()
    time.sleep(2)
    t4.start()
    time.sleep(2)
    t5.start()
    time.sleep(1)
    t_tg.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Dừng toàn bộ hệ thống Penta-Bot (HUIT, VAA, IUH, UFM, OU).")


if __name__ == "__main__":
    main()
