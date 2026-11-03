import os
import sys
import json
import time
import asyncio
import threading
from datetime import datetime, timezone, timedelta

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import database

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def format_messenger_message(act: dict, is_reopened: bool = False, bot_name: str = "Yuki 4 (UFM)") -> str:
    """Format tin nhắn hoạt động UFM cho Messenger (không dùng @All vì Messenger không hỗ trợ mention kiểu Zalo)."""
    header = "⚡ [UFM - HOẠT ĐỘNG MỞ THÊM SLOT] ⚡" if is_reopened else "🔥 [UFM - THÔNG BÁO HOẠT ĐỘNG & ĐRL MỚI] 🔥"

    raw_id = act.get("raw_id", "")
    id_prefix = f"[{raw_id}] " if raw_id and not act.get("title", "").startswith(f"[{raw_id}]") else ""
    title = f"{id_prefix}{act.get('title', 'Không có tiêu đề')}"
    unit = act.get("unit", "Chưa rõ đơn vị")
    event_time = act.get("event_time", "Xem chi tiết tại cổng")
    location = act.get("location", "Theo thông báo của đơn vị")
    status = act.get("status", "Đang mở")
    points = act.get("points", 0)
    ctxh = act.get("ctxh", 0)
    group_criteria = act.get("group_criteria", "")
    reg_url = act.get("register_url") or "https://hoatdong.ufm.edu.vn/DangKy"

    lines = [
        header,
        "━━━━━━━━━━━━━━━━━━━━",
        f"📌 Hoạt động: {title}",
        f"🏢 Đơn vị tổ chức: {unit}"
    ]

    points_str_list = []
    if points > 0:
        points_str_list.append(f"+{points} ĐRL")
    if ctxh > 0:
        points_str_list.append(f"+{ctxh} CTXH")

    if points_str_list:
        lines.append(f"🎯 Điểm: {' | '.join(points_str_list)}")

    if event_time and event_time != "Chưa rõ thời gian":
        lines.append(f"⏰ Thời gian: {event_time}")

    if location and location != "Chưa rõ địa điểm":
        lines.append(f"📍 Địa điểm: {location}")

    if group_criteria:
        lines.append(f"📊 Nhóm: {group_criteria}")

    lines.append(f"👥 Trạng thái: {status}")

    lines.extend([
        "━━━━━━━━━━━━━━━━━━━━",
        "👉 Vào cổng đăng ký ngay:",
        reg_url,
        "━━━━━━━━━━━━━━━━━━━━",
        "🙏 Xin lỗi nếu thông báo này đã làm phiền các bạn!",
        f"🤖 {bot_name} (via Messenger)"
    ])

    return "\n".join(lines)


def _get_or_create_event_loop():
    """Lấy hoặc tạo event loop cho thread hiện tại."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
        return loop
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


class MessengerDispatcher:
    """Quản lý kết nối và gửi tin nhắn Facebook Messenger qua cookie (fbchat-muqit)."""

    def __init__(self, config_file=CONFIG_PATH, db_file=None):
        self.config_file = config_file
        self.db_file = db_file
        self.client = None
        self._loop = None
        self._cookies_file = os.path.join(os.path.dirname(os.path.abspath(config_file)), "fb_cookies.json")
        self.load_config()

    def load_config(self):
        with open(self.config_file, "r", encoding="utf-8") as f:
            self.full_cfg = json.load(f)
            self.messenger_cfg = self.full_cfg.get("messenger", {})
            self.bot_name = self.full_cfg.get("bot_name", "Yuki 4 (UFM)")

    def _write_cookies_file(self, cookies_data):
        """Ghi cookies ra file JSON để fbchat-muqit đọc."""
        with open(self._cookies_file, "w", encoding="utf-8") as f:
            json.dump(cookies_data, f, ensure_ascii=False, indent=2)

    def connect(self) -> bool:
        """Kết nối tới Facebook Messenger bằng cookie."""
        self.load_config()
        cookies = self.messenger_cfg.get("cookies")
        if not cookies:
            print("⚠️ [Messenger] Chưa có cookies Facebook trong config.json -> mục 'messenger.cookies'")
            try:
                database.set_bot_status("messenger_cookie_status", "missing", db_file=self.db_file)
            except Exception:
                pass
            return False

        try:
            from fbchat_muqit import Client
        except ImportError:
            print("❌ [Messenger] Chưa cài thư viện fbchat-muqit. Chạy: pip install fbchat-muqit")
            try:
                database.set_bot_status("messenger_cookie_status", "missing_lib", db_file=self.db_file)
            except Exception:
                pass
            return False

        try:
            print("🔄 [Messenger] Đang kết nối tới Facebook Messenger...")

            # Ghi cookies ra file tạm cho fbchat-muqit
            self._write_cookies_file(cookies)

            # Tạo event loop riêng cho Messenger
            self._loop = asyncio.new_event_loop()

            async def _connect():
                client = Client(cookies_file_path=self._cookies_file)
                # Thử kiểm tra kết nối bằng cách fetch thông tin cơ bản
                if hasattr(client, 'uid') and client.uid:
                    return client
                # Một số phiên bản cần start_session
                if hasattr(client, 'start_session'):
                    await client.start_session()
                return client

            self.client = self._loop.run_until_complete(_connect())

            uid = getattr(self.client, 'uid', 'unknown')
            print(f"✅ [Messenger] Đăng nhập Facebook thành công! UID: {uid}")
            try:
                database.set_bot_status("messenger_cookie_status", "valid", db_file=self.db_file)
                database.set_bot_status("messenger_cookie_error", "", db_file=self.db_file)
                database.set_bot_status("messenger_account_uid", str(uid), db_file=self.db_file)
                database.set_bot_status("messenger_last_connected", database.get_vn_now_str(), db_file=self.db_file)
            except Exception:
                pass
            return True

        except Exception as e:
            err_msg = str(e)
            print(f"❌ [Messenger] Lỗi kết nối Facebook: {err_msg}")
            try:
                database.set_bot_status("messenger_cookie_status", "expired", db_file=self.db_file)
                database.set_bot_status("messenger_cookie_error", err_msg, db_file=self.db_file)
                database.log_event("WARN", f"[Messenger] Cookie Facebook hết hạn hoặc lỗi: {err_msg}", db_file=self.db_file)
            except Exception:
                pass
            self.client = None
            return False

    def _run_async(self, coro):
        """Chạy coroutine async trong event loop của Messenger."""
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
        return self._loop.run_until_complete(coro)

    def send_activity_alert(self, act: dict, is_reopened: bool = False, db_file=None) -> bool:
        """Gửi thông báo hoạt động UFM tới tất cả nhóm Messenger đang bật."""
        self.load_config()
        configured_groups = self.messenger_cfg.get("target_groups")
        if configured_groups is not None:
            target_list = [t for t in configured_groups if t.get("enabled") is True or str(t.get("enabled", "")).lower() in ("true", "1")]
            if not target_list:
                print("⏸️ [Messenger] Tất cả nhóm Messenger đều đang TẮT. Không gửi.")
                return False
        else:
            return False

        if not target_list:
            return False

        if not self.client:
            if not self.connect():
                return False

        formatted_msg = format_messenger_message(act, is_reopened=is_reopened, bot_name=self.bot_name)
        any_success = False

        for target in target_list:
            tid = str(target.get("id"))
            tname = target.get("name", tid)

            # Kiểm tra chống trùng lặp (dùng prefix "MSG_" để phân biệt với Zalo)
            msg_target_id = f"MSG_{tid}"
            if database.is_activity_already_sent_zalo(str(act.get("activity_id", "")), title=act.get("title"), target_id=msg_target_id, db_file=db_file):
                print(f"🛑 [Chống lặp Messenger] Hoạt động [{act.get('title')}] đã được gửi tới {tname} ({tid}) trước đó, bỏ qua!")
                continue

            try:
                async def _send():
                    await self.client.send_message(
                        text=formatted_msg,
                        thread_id=tid
                    )

                self._run_async(_send())

                log_str = f"[{self.bot_name}] [Messenger] Đã gửi thông báo tới nhóm [{tname}] (ID: {tid})"
                print(f"📨 [Messenger] {log_str}")
                database.log_event("MESSENGER", log_str, db_file=db_file)
                database.record_delivery(
                    post_id=act.get("activity_id", ""),
                    post_title=act.get("title", ""),
                    source_page=act.get("source", "UFM Portal"),
                    author=act.get("unit", "UFM"),
                    post_url=act.get("detail_url", "https://hoatdong.ufm.edu.vn/DangKy"),
                    content_snippet=formatted_msg[:3000],
                    has_form=1,
                    matched_keyword=f"+{act.get('points', 0)} ĐRL",
                    zalo_target_id=msg_target_id,
                    zalo_target_name=f"[Messenger] {tname}",
                    target_type="MESSENGER_GROUP",
                    status="SUCCESS",
                    crawled_at=database.get_vn_now_str(),
                    db_file=db_file
                )
                any_success = True

            except Exception as e:
                err_str = f"[Messenger] Lỗi gửi tin tới {tname} ({tid}): {e}"
                print(f"❌ {err_str}")
                database.log_event("ERROR", err_str, db_file=db_file)

                err_lower = str(e).lower()
                if any(w in err_lower for w in ["session", "expire", "auth", "login", "cookie", "token", "unauthorized", "invalid", "logout", "logged out"]):
                    try:
                        database.set_bot_status("messenger_cookie_status", "expired", db_file=self.db_file)
                        database.set_bot_status("messenger_cookie_error", f"Phiên Messenger hết hạn: {e}", db_file=self.db_file)
                    except Exception:
                        pass

                database.record_delivery(
                    post_id=act.get("activity_id", ""),
                    post_title=act.get("title", ""),
                    source_page=act.get("source", "UFM Portal"),
                    author=act.get("unit", "UFM"),
                    post_url=act.get("detail_url", "https://hoatdong.ufm.edu.vn/DangKy"),
                    content_snippet=str(err_str)[:1000],
                    has_form=1,
                    matched_keyword=f"+{act.get('points', 0)} ĐRL",
                    zalo_target_id=msg_target_id,
                    zalo_target_name=f"[Messenger] {tname}",
                    target_type="MESSENGER_GROUP",
                    status="FAILED",
                    crawled_at=database.get_vn_now_str(),
                    db_file=db_file
                )

        return any_success

    def send_test_message(self, target_thread_id=None, db_file=None) -> tuple:
        """Gửi tin nhắn thử nghiệm tới một nhóm Messenger cụ thể."""
        if not self.client:
            if not self.connect():
                return False, "Không thể kết nối tới Facebook Messenger (Cookie đã hết hạn hoặc bị hủy)"

        test_act = {
            "activity_id": f"MSG_TEST_{int(time.time())}",
            "raw_id": "TEST",
            "title": "Hoạt động Thử Nghiệm Hệ Thống Bot UFM (Messenger)",
            "unit": "Phòng Công tác sinh viên - Đại học Tài chính - Marketing (UFM)",
            "event_time": database.get_vn_now_str(),
            "location": "Trường ĐH Tài chính - Marketing",
            "group_criteria": "3.a.1 - Rèn luyện thể chất & kỹ năng sinh viên",
            "points": 5.0,
            "ctxh": 10.0,
            "status": "Đang mở đăng ký (Thử nghiệm)",
            "detail_url": "https://hoatdong.ufm.edu.vn/DangKy",
            "register_url": "https://hoatdong.ufm.edu.vn/DangKy",
            "source": "Thử nghiệm Messenger từ Web Dashboard UFM"
        }

        msg_text = format_messenger_message(test_act, is_reopened=False, bot_name=self.bot_name)

        if target_thread_id:
            tid = str(target_thread_id)
            try:
                async def _send():
                    await self.client.send_message(text=msg_text, thread_id=tid)

                self._run_async(_send())
                database.log_event("TEST", f"[Messenger] Đã gửi tin thử nghiệm tới nhóm {tid}", db_file=db_file)
                return True, f"Đã gửi tin thử nghiệm Messenger thành công tới ID {tid}!"
            except Exception as e:
                return False, f"[Messenger] Lỗi gửi tin: {e}"

        # Nếu không chỉ định target, gửi tới nhóm Messenger đầu tiên trong danh sách
        self.load_config()
        groups = self.messenger_cfg.get("target_groups", [])
        enabled_groups = [g for g in groups if g.get("enabled")]
        if not enabled_groups:
            return False, "Không có nhóm Messenger nào đang bật để gửi thử nghiệm."

        first_group = enabled_groups[0]
        tid = str(first_group["id"])
        tname = first_group.get("name", tid)
        try:
            async def _send():
                await self.client.send_message(text=msg_text, thread_id=tid)

            self._run_async(_send())
            database.log_event("TEST", f"[Messenger] Đã gửi tin thử nghiệm tới nhóm [{tname}] ({tid})", db_file=db_file)
            return True, f"Đã gửi tin thử nghiệm Messenger tới nhóm [{tname}] (ID: {tid})!"
        except Exception as e:
            return False, f"[Messenger] Lỗi gửi tin thử nghiệm: {e}"

    def fetch_all_groups(self) -> list:
        """Lấy danh sách tất cả nhóm chat Messenger của tài khoản."""
        if not self.client:
            if not self.connect():
                return []

        try:
            async def _fetch():
                threads = await self.client.fetch_thread_list(limit=50)
                group_list = []
                for thread in threads:
                    # Chỉ lấy nhóm (GROUP), bỏ qua chat cá nhân
                    t_type = getattr(thread, 'type', None)
                    t_name = getattr(thread, 'name', None) or ""
                    t_id = getattr(thread, 'id', None) or getattr(thread, 'uid', None)

                    # Kiểm tra xem có phải nhóm không (group thường có name và nhiều participants)
                    is_group = False
                    if t_type is not None:
                        t_type_str = str(t_type).lower()
                        if "group" in t_type_str:
                            is_group = True
                    # Nếu không xác định được type, kiểm tra dựa vào participants
                    if not is_group and hasattr(thread, 'participants') and thread.participants:
                        if len(thread.participants) > 2:
                            is_group = True

                    if t_id:
                        group_list.append({
                            "id": str(t_id),
                            "name": t_name or f"Nhóm {t_id}",
                            "is_group": is_group
                        })

                return group_list

            return self._run_async(_fetch())

        except Exception as e:
            print(f"❌ [Messenger] Lỗi lấy danh sách nhóm: {e}")
            return []
