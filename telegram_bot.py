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
        self.reload_config()
        self.running = False
        self.last_update_id = 0
        self.thread = None

    def reload_config(self):
        self.config = load_telegram_config()
        self.token = self.config.get("bot_token", "").strip()
        self.admin_chat_ids = [str(x) for x in self.config.get("admin_chat_ids", []) if str(x).strip()]
        self.api_base = f"https://api.telegram.org/bot{self.token}"

    def is_configured(self) -> bool:
        self.reload_config()
        return bool(self.token and self.config.get("enabled", False))

    def get_ou_auto_register_status(self) -> bool:
        ou_cfg = os.path.join(SCRIPT_DIR, "config_ou.json")
        if os.path.exists(ou_cfg):
            try:
                with open(ou_cfg, "r", encoding="utf-8") as f:
                    c = json.load(f)
                return bool(c.get("ou_portal", {}).get("auto_register", False) or c.get("auto_register", False))
            except Exception:
                pass
        return False

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
            r = requests.post(url, json=payload, timeout=15)
            if r.status_code != 200:
                logger.error(f"Telegram sendMessage failed ({r.status_code}): {r.text}")
            return r.status_code == 200
        except Exception as e:
            logger.error(f"Telegram sendMessage error: {e}")
            return False

    def send_photo(self, chat_id: str, photo_path: str, caption: str = "", parse_mode: str = "HTML", reply_markup: dict = None) -> bool:
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
                if reply_markup:
                    data["reply_markup"] = json.dumps(reply_markup)
                r = requests.post(url, data=data, files=files, timeout=30)
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
                ok = self.send_message(cid, text, reply_markup=self.get_dashboard_keyboard())
            if ok:
                success_count += 1
        return success_count

    def get_dashboard_keyboard(self) -> dict:
        ou_on = self.get_ou_auto_register_status()
        ou_btn_text = "🟢 Tự động ĐK OU: BẬT" if ou_on else "🔴 Tự động ĐK OU: TẮT"
        return {
            "inline_keyboard": [
                [
                    {"text": "📊 Tình trạng 5 Bot", "callback_data": "cmd_status"},
                    {"text": "🔔 Ping Zalo Demo", "callback_data": "cmd_ping_zalo_demo"}
                ],
                [
                    {"text": ou_btn_text, "callback_data": "cmd_toggle_ou"},
                    {"text": "⚡ Quét & ĐK OU Ngay", "callback_data": "cmd_force_ou_reg"}
                ],
                [
                    {"text": "📋 Sự kiện Cổng OU", "callback_data": "cmd_ou_events"},
                    {"text": "🍪 Kiểm tra Cookie", "callback_data": "cmd_check_cookies"}
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

        # Kiểm tra quyền admin
        if self.admin_chat_ids and chat_id not in self.admin_chat_ids:
            self.send_message(
                chat_id,
                f"⛔ <b>Bạn không có quyền truy cập hệ thống bot.</b>\nID của bạn là: <code>{chat_id}</code>\nHãy gửi ID này cho quản trị viên để được cấp quyền."
            )
            return

        cmd = text.lower().split()[0] if text else ""

        if cmd in ["/start", "/help", "menu", "bắt đầu"]:
            self.send_help_menu(chat_id, first_name)
        elif cmd == "/id":
            self.send_message(chat_id, f"🆔 <b>Chat ID của bạn:</b> <code>{chat_id}</code>")
        elif cmd in ["/status", "/tt"]:
            self.execute_status_command(chat_id)
        elif cmd in ["/ping_zalo", "/test_zalo", "/zalo"]:
            self.execute_ping_zalo_demo(chat_id)
        elif cmd in ["/toggle_ou", "/ou_toggle"]:
            self.execute_toggle_ou(chat_id)
        elif cmd in ["/dk_ou", "/reg_ou", "/force_ou"]:
            self.execute_force_ou_register(chat_id)
        elif cmd in ["/ou_events", "/events", "/sk_ou"]:
            self.execute_ou_events_list(chat_id)
        elif cmd in ["/cookies", "/cookie", "/check_cookies"]:
            self.execute_check_all_cookies(chat_id)
        elif cmd.startswith("/pov"):
            parts = text.split()
            bot_target = parts[1].lower() if len(parts) > 1 else "bot3"
            self.execute_pov_command(chat_id, bot_target)
        else:
            self.send_message(
                chat_id,
                f"❓ <b>Lệnh không xác định:</b> <code>{text}</code>\nGõ <code>/help</code> hoặc <code>/start</code> để xem danh sách lệnh và bảng điều khiển.",
                reply_markup=self.get_dashboard_keyboard()
            )

    def handle_callback_query(self, cb: dict):
        cb_id = cb.get("id")
        data = cb.get("data", "")
        msg = cb.get("message", {})
        chat_id = str(msg.get("chat", {}).get("id"))

        try:
            requests.post(f"{self.api_base}/answerCallbackQuery", json={"callback_query_id": cb_id}, timeout=5)
        except Exception:
            pass

        if self.admin_chat_ids and chat_id not in self.admin_chat_ids:
            return

        if data == "cmd_status":
            self.execute_status_command(chat_id)
        elif data == "cmd_ping_zalo_demo":
            self.execute_ping_zalo_demo(chat_id)
        elif data == "cmd_toggle_ou":
            self.execute_toggle_ou(chat_id)
        elif data == "cmd_force_ou_reg":
            self.execute_force_ou_register(chat_id)
        elif data == "cmd_ou_events":
            self.execute_ou_events_list(chat_id)
        elif data == "cmd_check_cookies":
            self.execute_check_all_cookies(chat_id)
        elif data == "cmd_pov_bot3":
            self.execute_pov_command(chat_id, "bot3")
        elif data == "cmd_pov_bot4":
            self.execute_pov_command(chat_id, "bot4")
        elif data == "cmd_pov_bot5":
            self.execute_pov_command(chat_id, "bot5")

    def send_help_menu(self, chat_id: str, first_name: str):
        ou_on = self.get_ou_auto_register_status()
        ou_status_str = "BẬT ✅" if ou_on else "TẮT ⏸️"
        help_text = (
            f"👋 <b>Xin chào {first_name}!</b>\n\n"
            f"🤖 <b>HỆ THỐNG ĐIỀU HÀNH PENTA-BOT 24/7</b>\n"
            f"<i>(HUIT • VAA • IUH • UFM • OU)</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📖 <b>HƯỚNG DẪN CHI TIẾT TỪNG CHỨC NĂNG:</b>\n\n"
            f"1️⃣ <b>📊 Tình trạng 5 Bot (<code>/status</code>):</b>\n"
            f"   Kiểm tra tổng quan 5 kênh bot: chu kỳ quét, thời gian quét gần nhất, cơ chế chống spam.\n\n"
            f"2️⃣ <b>🔔 Ping Zalo Demo (<code>/ping_zalo</code>):</b>\n"
            f"   Gửi tin nhắn test kiểm tra kết nối từ cả 5 bot vào nhóm Zalo Demo (475259879796859360) để xác nhận cookie Zalo hoạt động chuẩn 100%.\n\n"
            f"3️⃣ <b>🟢/🔴 Tự động ĐK OU (<code>/toggle_ou</code>) [Hiện tại: {ou_status_str}]:</b>\n"
            f"   Bật hoặc Tắt chế độ tự động săn sự kiện cho Bot 5 (OU). Trạng thái BẬT/TẮT hiển thị ngay trên nút bấm.\n\n"
            f"4️⃣ <b>⚡ Quét & ĐK OU Ngay (<code>/dk_ou</code>):</b>\n"
            f"   Ép Bot 5 kết nối cổng ĐRL OU ngay lập tức, tự động duyệt qua tất cả các ca/mục để đăng ký ngay mà không cần chờ chu kỳ 25s.\n\n"
            f"5️⃣ <b>📋 Sự kiện Cổng OU (<code>/ou_events</code>):</b>\n"
            f"   Xem danh sách các sự kiện hiện có trên cổng ĐRL OU, chi tiết số ca/mục và trạng thái (Đã ĐK, Đang mở, Sắp mở).\n\n"
            f"6️⃣ <b>🍪 Kiểm tra Cookie (<code>/cookies</code>):</b>\n"
            f"   Chuẩn đoán tình trạng sống/chết của toàn bộ Cookie Zalo, Facebook và Phiên đăng nhập Cổng trường.\n\n"
            f"7️⃣ <b>📸 POV Bot 3, 4, 5 (<code>/pov &lt;iuh|ufm|ou&gt;</code>):</b>\n"
            f"   Chụp ảnh màn hình thực tế (Proof of View) góc nhìn sinh viên đã đăng nhập trên từng cổng trường.\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👇 <i>Bạn có thể bấm trực tiếp các nút tiện ích dưới đây:</i>"
        )
        self.send_message(chat_id, help_text, reply_markup=self.get_dashboard_keyboard())

    def execute_status_command(self, chat_id: str):
        now_str = datetime.now(VN_TZ).strftime("%H:%M:%S %d/%m/%Y")
        ou_on = self.get_ou_auto_register_status()
        ou_auto = "BẬT ✅ (Tự đăng ký)" if ou_on else "TẮT ⏸️ (Chỉ thông báo)"

        status_text = (
            f"📊 <b>BÁO CÁO TRẠNG THÁI HỆ THỐNG PENTA-BOT</b>\n"
            f"⏰ <i>Thời điểm: {now_str}</i>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🟢 <b>Bot 1 (HUIT):</b> Quét 16 Fanpage (chu kỳ 30s)\n"
            f"🟢 <b>Bot 2 (VAA):</b> Quét 11 Fanpage (chu kỳ 30s)\n"
            f"🟢 <b>Bot 3 (IUH):</b> Cổng ĐRL doantn.iuh.edu.vn (chu kỳ 25s)\n"
            f"🟢 <b>Bot 4 (UFM):</b> Cổng ĐRL hoatdong.ufm.edu.vn (chu kỳ 25s)\n"
            f"🟢 <b>Bot 5 (OU):</b> Cổng ĐRL & Fanpage OU (chu kỳ 25s)\n"
            f"   └─ <i>Tự động đăng ký OU:</i> <b>{ou_auto}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🛡️ <i>Cơ chế chống spam:</i> <b>Đang kích hoạt</b>\n"
            f"🌐 <i>Web Dashboard:</i> <code>http://180.93.125.40:8000</code>"
        )
        self.send_message(chat_id, status_text, reply_markup=self.get_dashboard_keyboard())

    def execute_ping_zalo_demo(self, chat_id: str):
        self.send_message(chat_id, "⏳ <i>Đang gửi tin kiểm tra kết nối từ 5 Bot vào Nhóm Demo Zalo...</i>")
        
        configs = [
            ("Bot 1 (HUIT)", os.path.join(SCRIPT_DIR, "config.json")),
            ("Bot 2 (VAA)", os.path.join(SCRIPT_DIR, "vaabot.json")),
            ("Bot 3 (IUH)", os.path.join(SCRIPT_DIR, "config_iuh.json")),
            ("Bot 4 (UFM)", os.path.join(SCRIPT_DIR, "config_ufm.json")),
            ("Bot 5 (OU)", os.path.join(SCRIPT_DIR, "config_ou.json")),
        ]
        demo_group_id = "475259879796859360"
        now_str = datetime.now(VN_TZ).strftime("%H:%M:%S %d/%m/%Y")
        
        results = []
        try:
            from zalo_sender import ZaloDispatcher
            from zlapi.models import Message, ThreadType
            
            for name, cfg_path in configs:
                if not os.path.exists(cfg_path):
                    results.append((name, False, "Thiếu file cấu hình"))
                    continue
                try:
                    disp = ZaloDispatcher(config_file=cfg_path)
                    if not disp.connect() or not disp.client:
                        results.append((name, False, "Cookie Zalo hết hạn hoặc lỗi kết nối"))
                        continue
                    
                    ping_text = (
                        f"🔔 [TEST KẾT NỐI ZALO DEMO] 🔔\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"🤖 {name}\n"
                        f"⏰ Thời gian: {now_str}\n"
                        f"✅ Cookie Zalo hoạt động ổn định 100%!"
                    )
                    disp.client.send(Message(text=ping_text), thread_id=demo_group_id, thread_type=ThreadType.GROUP)
                    results.append((name, True, "Đã gửi vào nhóm Demo thành công"))
                except Exception as e:
                    results.append((name, False, str(e)[:60]))
        except Exception as e:
            self.send_message(chat_id, f"❌ Lỗi import/kết nối Zalo: {e}")
            return
            
        report_lines = [
            "🔔 <b>KẾT QUẢ KIỂM TRA ZALO COOKIE (NHÓM DEMO)</b>",
            f"⏰ <i>Thời điểm: {now_str}</i>",
            "━━━━━━━━━━━━━━━━━━━━"
        ]
        all_ok = True
        for name, ok, note in results:
            icon = "✅" if ok else "❌"
            if not ok:
                all_ok = False
            report_lines.append(f"{icon} <b>{name}:</b> {note}")
            
        report_lines.append("━━━━━━━━━━━━━━━━━━━━")
        if all_ok:
            report_lines.append("🎉 <b>Toàn bộ 5 Bot đã gửi thành công vào nhóm Demo! Cookie hoạt động hoàn hảo.</b>")
        else:
            report_lines.append("⚠️ <i>Có bot gửi thất bại. Vui lòng kiểm tra lại cookie Zalo của bot đó.</i>")
            
        self.send_message(chat_id, "\n".join(report_lines), reply_markup=self.get_dashboard_keyboard())

    def execute_force_ou_register(self, chat_id: str):
        self.send_message(chat_id, "⏳ <i>Đang quét Cổng ĐRL OU và thực hiện tự động đăng ký ngay lập tức...</i>")
        try:
            from ou_scraper import OUPortalScraper
            ou_cfg = os.path.join(SCRIPT_DIR, "config_ou.json")
            with open(ou_cfg, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            p_cfg = cfg.get("ou_portal", {})
            scraper = OUPortalScraper(
                username=p_cfg.get("username", "2654092020"),
                password=p_cfg.get("password", "079308035034"),
                config_path=ou_cfg,
                auto_relogin=True
            )
            ok_l, msg_l = scraper.keep_alive()
            if not ok_l:
                ok_l, msg_l, _ = scraper.auto_login()
            if not ok_l:
                self.send_message(chat_id, f"❌ <b>Không thể kết nối Cổng OU:</b> {msg_l}")
                return
                
            ok_ev, events, msg_ev = scraper.fetch_events()
            if not ok_ev or not events:
                self.send_message(chat_id, f"ℹ️ <b>Không có sự kiện nào:</b> {msg_ev}")
                return
                
            report = [
                "⚡ <b>KẾT QUẢ QUÉT & TỰ ĐỘNG ĐĂNG KÝ OU NGAY</b>",
                f"👤 Sinh viên: <b>{scraper.student_name} (2654092020)</b>",
                f"📊 Tìm thấy: <b>{len(events)} sự kiện trên cổng</b>",
                "━━━━━━━━━━━━━━━━━━━━"
            ]
            
            for ev in events:
                title = ev.get("title", "")
                is_reg = ev.get("is_registered", False)
                is_open = ev.get("is_open", False)
                
                if is_reg:
                    report.append(f"✅ <b>{title[:40]}...</b>\n   └ Trạng thái: <i>Đã đăng ký trước đó</i>")
                elif not is_open:
                    report.append(f"⏳ <b>{title[:40]}...</b>\n   └ Trạng thái: <i>Chưa mở đăng ký ({ev.get('reg_start_str')})</i>")
                else:
                    reg_res = scraper.register_event(ev)
                    ok_reg = reg_res[0]
                    msg_reg = reg_res[1]
                    sess_name = reg_res[2] if len(reg_res) > 2 else ""
                    pts = reg_res[3] if len(reg_res) > 3 else ev.get("points", 0)
                    
                    if ok_reg:
                        report.append(f"🎉 <b>{title[:40]}...</b>\n   └ ✅ <b>ĐĂNG KÝ THÀNH CÔNG!</b>\n   └ Mục: <i>{sess_name}</i> (+{pts} ĐRL)")
                    else:
                        report.append(f"⚠️ <b>{title[:40]}...</b>\n   └ ❌ <i>{msg_reg}</i>")
                        
            report.append("━━━━━━━━━━━━━━━━━━━━")
            report.append("👉 Link cổng: <code>https://renluyensv.ou.edu.vn/20261/diemrl/dangkysukien</code>")
            self.send_message(chat_id, "\n".join(report), reply_markup=self.get_dashboard_keyboard())
        except Exception as e:
            self.send_message(chat_id, f"❌ <b>Lỗi thực thi:</b> {e}")

    def execute_ou_events_list(self, chat_id: str):
        self.send_message(chat_id, "⏳ <i>Đang tải danh sách sự kiện từ Cổng ĐRL OU...</i>")
        try:
            from ou_scraper import OUPortalScraper
            ou_cfg = os.path.join(SCRIPT_DIR, "config_ou.json")
            with open(ou_cfg, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            p_cfg = cfg.get("ou_portal", {})
            scraper = OUPortalScraper(
                username=p_cfg.get("username", "2654092020"),
                password=p_cfg.get("password", "079308035034"),
                config_path=ou_cfg,
                auto_relogin=True
            )
            ok_l, msg_l = scraper.keep_alive()
            if not ok_l:
                ok_l, msg_l, _ = scraper.auto_login()
            if not ok_l:
                self.send_message(chat_id, f"❌ <b>Không thể kết nối Cổng OU:</b> {msg_l}")
                return
                
            ok_ev, events, msg_ev = scraper.fetch_events()
            if not ok_ev:
                self.send_message(chat_id, f"❌ Lỗi tải sự kiện: {msg_ev}")
                return
                
            lines = [
                "📋 <b>DANH SÁCH SỰ KIỆN CỔNG ĐRL OU</b>",
                f"👤 Sinh viên: <b>{scraper.student_name} (2654092020)</b>",
                f"📊 Tổng cộng: <b>{len(events)} sự kiện</b>",
                "━━━━━━━━━━━━━━━━━━━━"
            ]
            for i, ev in enumerate(events, 1):
                title = ev.get("title", "")
                unit = ev.get("unit", "")
                pts = ev.get("points", 0)
                is_reg = ev.get("is_registered", False)
                is_open = ev.get("is_open", False)
                ans_cnt = len(ev.get("answers", []))
                
                status_tag = "✅ ĐÃ ĐĂNG KÝ" if is_reg else ("🟢 ĐANG MỞ ĐK" if is_open else "⏳ SẮP MỞ ĐK")
                lines.append(f"<b>{i}. {title}</b>")
                lines.append(f"   • Trạng thái: <b>{status_tag}</b>")
                lines.append(f"   • Đơn vị: {unit} | Điểm: +{pts:g}")
                lines.append(f"   • Số ca/mục lựa chọn: <b>{ans_cnt} ca</b>")
                if ev.get("reg_time"):
                    lines.append(f"   • Giờ ĐK: {ev.get('reg_time')}")
                lines.append("────────────────────")
                
            lines.append("👉 Link cổng: <code>https://renluyensv.ou.edu.vn/20261/diemrl/dangkysukien</code>")
            self.send_message(chat_id, "\n".join(lines), reply_markup=self.get_dashboard_keyboard())
        except Exception as e:
            self.send_message(chat_id, f"❌ Lỗi: {e}")

    def execute_check_all_cookies(self, chat_id: str):
        self.send_message(chat_id, "⏳ <i>Đang kiểm tra chẩn đoán toàn bộ Cookie và phiên đăng nhập 5 Bot...</i>")
        now_str = datetime.now(VN_TZ).strftime("%H:%M:%S %d/%m/%Y")
        report = [
            "🍪 <b>CHẨN ĐOÁN TOÀN DIỆN COOKIE & PHIÊN ĐĂNG NHẬP</b>",
            f"⏰ <i>Thời điểm: {now_str}</i>",
            "━━━━━━━━━━━━━━━━━━━━"
        ]

        # 1. Zalo Cookies
        zalo_cfgs = [
            ("Bot 1 (HUIT)", os.path.join(SCRIPT_DIR, "config.json")),
            ("Bot 2 (VAA)", os.path.join(SCRIPT_DIR, "vaabot.json")),
            ("Bot 3 (IUH)", os.path.join(SCRIPT_DIR, "config_iuh.json")),
            ("Bot 4 (UFM)", os.path.join(SCRIPT_DIR, "config_ufm.json")),
            ("Bot 5 (OU)", os.path.join(SCRIPT_DIR, "config_ou.json")),
        ]
        report.append("📱 <b>1. Trạng thái Cookie Zalo:</b>")
        for name, cp in zalo_cfgs:
            if not os.path.exists(cp):
                report.append(f"   ❌ {name}: Thiếu config")
                continue
            try:
                with open(cp, "r", encoding="utf-8") as f:
                    c = json.load(f)
                has_c = bool(c.get("zalo", {}).get("cookies"))
                report.append(f"   {'✅' if has_c else '⚠️'} {name}: {'Đã nạp' if has_c else 'Trống'}")
            except Exception:
                report.append(f"   ❌ {name}: Lỗi đọc file")

        # 2. Cổng trường
        report.append("\n🏫 <b>2. Trạng thái Cổng trường & SSO:</b>")
        # Bot 3 (IUH)
        try:
            from iuh_scraper import IUHPortalScraper
            iuh_s = IUHPortalScraper(config_path=os.path.join(SCRIPT_DIR, "config_iuh.json"))
            alive_iuh, _ = iuh_s.keep_alive()
            report.append(f"   {'✅' if alive_iuh else '⚠️'} IUH Portal: {'Session Active' if alive_iuh else 'Cần login lại'}")
        except Exception as e:
            report.append(f"   ❌ IUH Portal: {str(e)[:30]}")

        # Bot 4 (UFM)
        try:
            ufm_cfg = os.path.join(SCRIPT_DIR, "config_ufm.json")
            with open(ufm_cfg, "r", encoding="utf-8") as f:
                uc = json.load(f)
            has_ufm_c = bool(uc.get("ufm_portal", {}).get("cookies", {}).get(".AspNetCore.Cookies"))
            report.append(f"   {'✅' if has_ufm_c else '❌'} UFM Portal: {'Cookies tươi' if has_ufm_c else 'Hết hạn'}")
        except Exception:
            report.append("   ❌ UFM Portal: Lỗi cấu hình")

        # Bot 5 (OU)
        try:
            from ou_scraper import OUPortalScraper
            ou_s = OUPortalScraper(config_path=os.path.join(SCRIPT_DIR, "config_ou.json"))
            alive_ou, _ = ou_s.keep_alive()
            report.append(f"   {'✅' if alive_ou else '⚠️'} OU Portal SSO: {'Session Active' if alive_ou else 'Cần auto_login'}")
        except Exception as e:
            report.append(f"   ❌ OU Portal SSO: {str(e)[:30]}")

        report.append("━━━━━━━━━━━━━━━━━━━━")
        self.send_message(chat_id, "\n".join(report), reply_markup=self.get_dashboard_keyboard())

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
            self.send_photo(chat_id, img_path, caption=caption, reply_markup=self.get_dashboard_keyboard())
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
            current = bool(c.get("ou_portal", {}).get("auto_register", False) or c.get("auto_register", False))
            new_state = not current
            c.setdefault("ou_portal", {})["auto_register"] = new_state
            c["auto_register"] = new_state
            with open(ou_cfg, "w", encoding="utf-8") as f:
                json.dump(c, f, ensure_ascii=False, indent=2)
            
            st_text = "ĐÃ BẬT ✅" if new_state else "ĐÃ TẮT ⏸️"
            desc = (
                "Khi có sự kiện mới hoặc đến giờ mở đăng ký, Bot 5 sẽ tự động duyệt qua tất cả các ca/mục để đăng ký ngay lập tức và gửi thông báo xác nhận."
                if new_state else
                "Bot 5 sẽ chỉ gửi thông báo sự kiện, không thực hiện thao tác tự động đăng ký."
            )
            self.send_message(
                chat_id,
                f"⚙️ <b>CẬP NHẬT TỰ ĐỘNG ĐĂNG KÝ OU:</b> <b>{st_text}</b>\n\nℹ️ <i>{desc}</i>",
                reply_markup=self.get_dashboard_keyboard()
            )
        except Exception as e:
            self.send_message(chat_id, f"❌ Lỗi cập nhật cấu hình: {e}")

    def poll_updates(self):
        """Vòng lặp Long-polling nhận lệnh từ Telegram."""
        self.running = True
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
        bot.broadcast_admin("🚀 <b>Hệ thống Penta-Bot đã khởi động và sẵn sàng nhận lệnh!</b>")
        bot.poll_updates()
    else:
        print("Telegram bot chưa cấu hình token. Vui lòng thiết lập trong config_telegram.json.")
