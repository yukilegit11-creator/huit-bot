import os
import sys
import json
import time
import logging
import threading
import requests
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger("telegram_bot")
VN_TZ = timezone(timedelta(hours=7))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config_telegram.json")

def load_telegram_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading {CONFIG_FILE}: {e}")
    return {
        "enabled": False,
        "bot_token": "",
        "admin_chat_ids": [],
        "notify_new_activities": True,
        "notify_auto_register": True,
        "notify_system_errors": True
    }

def save_telegram_config(cfg: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving {CONFIG_FILE}: {e}")

class TelegramController:
    """
    Module điều khiển và giám sát Penta-Bot qua Telegram Bot API chính thức.
    Sử dụng requests thuần túy, không phụ thuộc thư viện bên thứ 3.
    """
    def __init__(self, config_path: str = CONFIG_FILE):
        self.config_path = config_path
        self.config = load_telegram_config()
        self.token = self.config.get("bot_token", "").strip()
        self.admin_chat_ids = [str(x) for x in self.config.get("admin_chat_ids", []) if str(x).strip()]
        self.api_base = f"https://api.telegram.org/bot{self.token}"
        self.running = False
        self.last_update_id = 0
        self.thread = None

    def is_configured(self) -> bool:
        return bool(self.token and self.config.get("enabled", False))

    def send_message(self, chat_id: str, text: str, reply_markup: dict = None, parse_mode: str = "HTML") -> bool:
        if not self.token:
            return False
        url = f"{self.api_base}/sendMessage"
        payload = {
            "chat_id": str(chat_id),
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            r = requests.post(url, json=payload, timeout=12)
            return r.status_code == 200
        except Exception as e:
            logger.error(f"Telegram sendMessage error: {e}")
            return False

    def send_photo(self, chat_id: str, photo_path: str, caption: str = "", parse_mode: str = "HTML") -> bool:
        if not self.token or not os.path.exists(photo_path):
            return False
        url = f"{self.api_base}/sendPhoto"
        try:
            with open(photo_path, "rb") as f:
                files = {"photo": f}
                data = {
                    "chat_id": str(chat_id),
                    "caption": caption[:1024],
                    "parse_mode": parse_mode
                }
                r = requests.post(url, data=data, files=files, timeout=25)
                return r.status_code == 200
        except Exception as e:
            logger.error(f"Telegram sendPhoto error: {e}")
            return False

    def broadcast_admin(self, text: str, photo_path: str = None) -> int:
        """Gửi thông báo tới tất cả admin Telegram trong danh sách."""
        if not self.is_configured():
            return 0
        success_count = 0
        for cid in self.admin_chat_ids:
            if photo_path and os.path.exists(photo_path):
                ok = self.send_photo(cid, photo_path, caption=text)
            else:
                ok = self.send_message(cid, text)
            if ok:
                success_count += 1
        return success_count

    def get_dashboard_keyboard(self) -> dict:
        return {
            "inline_keyboard": [
                [
                    {"text": "📊 Tình trạng 5 Bot", "callback_data": "cmd_status"},
                    {"text": "🔄 Tự động ĐK OU", "callback_data": "cmd_toggle_ou"}
                ],
                [
                    {"text": "📸 POV Bot 3 (IUH)", "callback_data": "cmd_pov_bot3"},
                    {"text": "📸 POV Bot 4 (UFM)", "callback_data": "cmd_pov_bot4"}
                ],
                [
                    {"text": "📸 POV Bot 5 (OU)", "callback_data": "cmd_pov_bot5"}
                ]
            ]
        }

    def handle_message(self, msg: dict):
        chat = msg.get("chat", {})
        chat_id = str(chat.get("id"))
        user = msg.get("from", {})
        text = str(msg.get("text", "")).strip()
        first_name = user.get("first_name", "Admin")

        # Kiểm tra quyền: Chỉ phản hồi admin nếu danh sách admin_chat_ids đã thiết lập
        if self.admin_chat_ids and chat_id not in self.admin_chat_ids:
            self.send_message(
                chat_id,
                f"⛔ <b>Bạn không có quyền truy cập hệ thống bot.</b>\nID của bạn là: <code>{chat_id}</code>\nHãy gửi ID này cho quản trị viên để được cấp quyền."
            )
            return

        cmd = text.lower().split()[0] if text else ""

        if cmd in ["/start", "/help", "menu"]:
            welcome = (
                f"👋 <b>Xin chào {first_name}!</b>\n"
                f"🤖 <b>HỆ THỐNG ĐIỀU HÀNH PENTA-BOT 24/7</b>\n"
                f"<i>(HUIT • VAA • IUH • UFM • OU)</i>\n\n"
                f"📌 <b>Các lệnh điều khiển nhanh:</b>\n"
                f"• <code>/status</code> - Xem trạng thái hoạt động & tài nguyên VPS\n"
                f"• <code>/pov [bot3/bot4/bot5]</code> - Chụp màn hình góc nhìn thực tế\n"
                f"• <code>/toggle_ou</code> - Bật / Tắt tự động đăng ký Bot 5 (OU)\n"
                f"• <code>/id</code> - Xem Chat ID Telegram của bạn\n\n"
                f"👇 <i>Hoặc sử dụng các nút tương tác bên dưới:</i>"
            )
            self.send_message(chat_id, welcome, reply_markup=self.get_dashboard_keyboard())

        elif cmd == "/id":
            self.send_message(chat_id, f"🆔 <b>Chat ID của bạn:</b> <code>{chat_id}</code>")

        elif cmd == "/status":
            self.execute_status_command(chat_id)

        elif cmd.startswith("/pov"):
            parts = text.split()
            bot_target = parts[1].lower() if len(parts) > 1 else "bot3"
            self.execute_pov_command(chat_id, bot_target)

        elif cmd in ["/toggle_ou", "/toggle_ou_reg"]:
            self.execute_toggle_ou(chat_id)

        else:
            self.send_message(
                chat_id,
                f"❓ <b>Lệnh không xác định.</b> Gõ <code>/help</code> hoặc <code>/start</code> để mở bảng điều khiển."
            )

    def handle_callback_query(self, cb: dict):
        cb_id = cb.get("id")
        data = cb.get("data", "")
        msg = cb.get("message", {})
        chat_id = str(msg.get("chat", {}).get("id"))

        # Answer callback để tắt biểu tượng đồng hồ quay
        try:
            requests.post(f"{self.api_base}/answerCallbackQuery", json={"callback_query_id": cb_id}, timeout=5)
        except Exception:
            pass

        if self.admin_chat_ids and chat_id not in self.admin_chat_ids:
            return

        if data == "cmd_status":
            self.execute_status_command(chat_id)
        elif data == "cmd_toggle_ou":
            self.execute_toggle_ou(chat_id)
        elif data == "cmd_pov_bot3":
            self.execute_pov_command(chat_id, "bot3")
        elif data == "cmd_pov_bot4":
            self.execute_pov_command(chat_id, "bot4")
        elif data == "cmd_pov_bot5":
            self.execute_pov_command(chat_id, "bot5")

    def execute_status_command(self, chat_id: str):
        now_str = datetime.now(VN_TZ).strftime("%H:%M:%S %d/%m/%Y")
        
        # Đọc cấu hình các bot
        ou_cfg = os.path.join(SCRIPT_DIR, "config_ou.json")
        ou_auto = "TẮT"
        if os.path.exists(ou_cfg):
            try:
                with open(ou_cfg, "r", encoding="utf-8") as f:
                    c = json.load(f)
                ou_auto = "BẬT ✅" if c.get("auto_register", False) else "TẮT ⏸️"
            except Exception:
                pass

        status_text = (
            f"📊 <b>BÁO CÁO TRẠNG THÁI HỆ THỐNG PENTA-BOT</b>\n"
            f"⏰ <i>Thời điểm: {now_str}</i>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🟢 <b>Bot 1 (HUIT):</b> Quét 16 Fanpage (chu kỳ 30s)\n"
            f"🟢 <b>Bot 2 (VAA):</b> Quét 11 Fanpage (chu kỳ 30s)\n"
            f"🟢 <b>Bot 3 (IUH):</b> Cổng ĐRL doantn.iuh.edu.vn (chu kỳ 25s)\n"
            f"🟢 <b>Bot 4 (UFM):</b> Cổng ĐRL hoatdong.ufm.edu.vn (chu kỳ 25s)\n"
            f"🟢 <b>Bot 5 (OU):</b> Cổng ĐRL & Fanpage OU (chu kỳ 25s)\n"
            f"   └─ <i>Tự động đăng ký OU:</i> <b>{ou_auto}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🛡️ <i>Cơ chế chống spam:</i> <b>Đang kích hoạt</b>\n"
            f"🌐 <i>Web Dashboard:</i> <code>http://180.93.125.40:8000</code>"
        )
        self.send_message(chat_id, status_text, reply_markup=self.get_dashboard_keyboard())

    def execute_pov_command(self, chat_id: str, bot_key: str):
        bot_names = {
            "bot3": "Bot 3 - IUH",
            "bot4": "Bot 4 - UFM",
            "bot5": "Bot 5 - OU",
            "iuh": "Bot 3 - IUH",
            "ufm": "Bot 4 - UFM",
            "ou": "Bot 5 - OU"
        }
        bname = bot_names.get(bot_key.lower(), bot_key)
        self.send_message(chat_id, f"⏳ <i>Đang kết nối cổng trường và chụp ảnh POV thực tế cho {bname}... (khoảng 3-6s)</i>")
        
        try:
            import snapshot_service
            res = snapshot_service.capture_portal_view(bot_key, base_dir=SCRIPT_DIR, force=True)
            if not res or res.get("status") != "success":
                err = res.get("message", "Chụp ảnh thất bại") if res else "Không có phản hồi"
                self.send_message(chat_id, f"❌ <b>Chụp ảnh thất bại cho {bname}:</b>\n{err}")
                return

            real_key = snapshot_service.resolve_bot_key(bot_key)
            img_path = os.path.join(SCRIPT_DIR, "static", "snapshots", f"{real_key}_latest.png")
            if not os.path.exists(img_path):
                self.send_message(chat_id, f"❌ <b>Không tìm thấy file ảnh chụp tại:</b> <code>{img_path}</code>")
                return

            caption = (
                f"📸 <b>Góc Nhìn Thực Tế (POV): {res.get('portal_name')}</b>\n"
                f"🏫 {res.get('school')}\n"
                f"👤 {res.get('account_info')}\n"
                f"⏰ Lúc: {res.get('captured_at')}"
            )
            self.send_photo(chat_id, img_path, caption=caption)
        except Exception as e:
            self.send_message(chat_id, f"❌ <b>Lỗi hệ thống khi chụp ảnh:</b> {e}")

    def execute_toggle_ou(self, chat_id: str):
        ou_cfg = os.path.join(SCRIPT_DIR, "config_ou.json")
        if not os.path.exists(ou_cfg):
            self.send_message(chat_id, "❌ Không tìm thấy config_ou.json")
            return
        try:
            with open(ou_cfg, "r", encoding="utf-8") as f:
                c = json.load(f)
            current = c.get("auto_register", False)
            new_state = not current
            c["auto_register"] = new_state
            with open(ou_cfg, "w", encoding="utf-8") as f:
                json.dump(c, f, ensure_ascii=False, indent=2)
            
            st_text = "ĐÃ BẬT ✅ (Sẽ tự đăng ký khi có sự kiện mở)" if new_state else "ĐÃ TẮT ⏸️ (Chỉ thông báo, không tự đăng ký)"
            self.send_message(
                chat_id,
                f"⚙️ <b>Cập nhật cấu hình Bot 5 (OU):</b>\nChế độ tự động đăng ký: <b>{st_text}</b>",
                reply_markup=self.get_dashboard_keyboard()
            )
        except Exception as e:
            self.send_message(chat_id, f"❌ Lỗi cập nhật cấu hình: {e}")

    def poll_updates(self):
        """Vòng lặp Long-polling nhận lệnh từ Telegram."""
        logger.info("Telegram long-polling loop started.")
        while self.running:
            try:
                url = f"{self.api_base}/getUpdates?offset={self.last_update_id + 1}&timeout=20"
                r = requests.get(url, timeout=25)
                if r.status_code == 200:
                    data = r.json()
                    for item in data.get("result", []):
                        self.last_update_id = item.get("update_id", self.last_update_id)
                        if "message" in item:
                            self.handle_message(item["message"])
                        elif "callback_query" in item:
                            self.handle_callback_query(item["callback_query"])
                elif r.status_code == 401:
                    logger.error("Telegram Bot Token không hợp lệ (401 Unauthorized).")
                    time.sleep(10)
                else:
                    time.sleep(2)
            except requests.exceptions.Timeout:
                continue
            except Exception as e:
                logger.error(f"Telegram polling error: {e}")
                time.sleep(3)

    def start_polling(self):
        if not self.is_configured():
            logger.info("Telegram Bot chưa được kích hoạt (cần cấu hình bot_token và enabled=true).")
            return
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self.poll_updates, daemon=True)
        self.thread.start()
        logger.info("Telegram Controller thread initiated.")

    def stop_polling(self):
        self.running = False

# Singleton instance
_telegram_instance: Optional[TelegramController] = None

def get_telegram_bot() -> TelegramController:
    global _telegram_instance
    if _telegram_instance is None:
        _telegram_instance = TelegramController()
    return _telegram_instance

def send_telegram_alert(message: str, photo_path: str = None) -> int:
    """Hàm toàn cục để bất kỳ bot nào cũng có thể gửi thông báo về Telegram."""
    bot = get_telegram_bot()
    return bot.broadcast_admin(message, photo_path=photo_path)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Khởi chạy kiểm tra Telegram Controller...")
    bot = get_telegram_bot()
    if bot.is_configured():
        print(f"Token: {bot.token[:8]}... (Admins: {bot.admin_chat_ids})")
        bot.broadcast_admin("🚀 <b>Hệ thống Penta-Bot đã kết nối với Telegram thành công!</b>")
        bot.poll_updates()
    else:
        print("Telegram bot chưa cấu hình token. Vui lòng thiết lập trong config_telegram.json.")
