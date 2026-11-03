import os
import sys
import json
import time
import asyncio
import threading
import re
from datetime import datetime, timezone, timedelta

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Đảm bảo Windows sử dụng SelectorEventLoop cho socket / MQTT của fbchat-muqit
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

import database

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")


def extract_form_links(text: str) -> list:
    if not text:
        return []
    patterns = [
        r'https?://forms\.gle/[a-zA-Z0-9_\-]+',
        r'https?://docs\.google\.com/forms/[^\s\)\"\'>]+',
        r'https?://docs\.google\.com/document/[^\s\)\"\'>]+',
        r'https?://docs\.google\.com/spreadsheets/[^\s\)\"\'>]+',
        r'https?://forms\.office\.com/[^\s\)\"\'>]+',
        r'https?://(?:bit\.ly|tinyurl\.com|shorturl\.at)/[a-zA-Z0-9_\-]+',
    ]
    found = []
    for pat in patterns:
        matches = re.findall(pat, text, re.IGNORECASE)
        for m in matches:
            clean_m = m.rstrip('.,;:)')
            if clean_m not in found:
                found.append(clean_m)
    return found


def extract_post_title(text: str, max_len: int = 150) -> str:
    if not text:
        return "Thông báo mới"
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    if not lines:
        return "Thông báo mới"
    first_line = lines[0]
    if len(first_line) < 15 and len(lines) > 1:
        first_line = f"{first_line} - {lines[1]}"
    if len(first_line) > max_len:
        first_line = first_line[:max_len].rsplit(" ", 1)[0] + "..."
    return first_line


def format_post_messenger_message(post_data: dict, page_name: str, bot_name: str = "Yuki Bot") -> str:
    """Format bài viết mạng xã hội (HUIT, VAA) cho Messenger."""
    posted_time = post_data.get("posted_time", "").strip() or "Vừa xong"
    text = post_data.get("content", "").strip()
    url = post_data.get("post_url", "").strip()
    title = extract_post_title(text)
    form_links = extract_form_links(text)

    lines = []
    if form_links:
        lines.append("⚡ [PHÁT HIỆN FORM ĐĂNG KÝ SỰ KIỆN] ⚡")
        lines.append(f"📌 Tiêu đề: {title}")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("📝 LINK FORM ĐĂNG KÝ:")
        for flink in form_links:
            lines.append(f"👉 {flink}")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"🏢 Nguồn đăng: {page_name}")
        lines.append(f"⏰ Thời gian: {posted_time}")
    else:
        lines.append("📢 [BÀI ĐĂNG MỚI] 📢")
        lines.append(f"📌 {title}")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"🏢 Đăng bởi: {page_name}")
        lines.append(f"⏰ Thời gian: {posted_time}")

    # Nội dung trích dẫn
    if text:
        content_preview = text if len(text) <= 500 else text[:500] + "..."
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"📄 Nội dung:\n{content_preview}")

    if url:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"🔗 Xem bài viết gốc:\n{url}")

    lines.extend([
        "━━━━━━━━━━━━━━━━━━━━",
        "🙏 Xin lỗi nếu thông báo này đã làm phiền các bạn!",
        f"🤖 {bot_name} (Facebook Messenger)"
    ])

    return "\n".join(lines)


def format_activity_messenger_message(act: dict, is_reopened: bool = False, bot_name: str = "Yuki Bot", unit_label: str = "Đơn vị") -> str:
    """Format hoạt động/sự kiện ĐRL (IUH, UFM) cho Messenger."""
    header = "⚡ [HOẠT ĐỘNG MỞ THÊM SLOT] ⚡" if is_reopened else "🔥 [THÔNG BÁO HOẠT ĐỘNG & ĐRL MỚI] 🔥"

    raw_id = act.get("raw_id", "")
    id_prefix = f"[{raw_id}] " if raw_id and not act.get("title", "").startswith(f"[{raw_id}]") else ""
    title = f"{id_prefix}{act.get('title', 'Không có tiêu đề')}"
    unit = act.get("unit") or act.get("organizer") or "Chưa rõ đơn vị"
    event_time = act.get("event_time") or act.get("time") or "Xem chi tiết tại cổng"
    location = act.get("location", "Theo thông báo của đơn vị")
    status = act.get("status", "Đang mở")
    points = act.get("points", 0)
    ctxh = act.get("ctxh", 0)
    semester = act.get("semester", "")
    reg_url = act.get("register_url") or act.get("url") or "Xem tại cổng trường"

    lines = [
        header,
        "━━━━━━━━━━━━━━━━━━━━",
        f"📌 Hoạt động: {title}",
        f"🏢 {unit_label}: {unit}"
    ]

    now_vn = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S %d/%m/%Y")
    posted_time = act.get("posted_time") or act.get("first_seen") or now_vn

    points_str_list = []
    if points > 0:
        points_str_list.append(f"+{points:g} ĐRL")
    if ctxh > 0:
        points_str_list.append(f"+{ctxh:g} CTXH")
    if semester:
        points_str_list.append(f"HK: {semester}")

    if points_str_list:
        lines.append(f"🎯 Điểm: {' • '.join(points_str_list)}")

    lines.append(f"⏰ Thời gian đăng bài: {posted_time}")

    if event_time and event_time != "Chưa rõ thời gian":
        lines.append(f"📅 Thời gian diễn ra: {event_time}")

    if location and location != "Chưa rõ địa điểm":
        lines.append(f"📍 Địa điểm: {location}")

    lines.append(f"👥 Trạng thái: {status}")

    lines.extend([
        "━━━━━━━━━━━━━━━━━━━━",
        "👉 Vào cổng đăng ký ngay:",
        reg_url,
        "━━━━━━━━━━━━━━━━━━━━",
        "🙏 Xin lỗi nếu thông báo này đã làm phiền các bạn!",
        f"🤖 {bot_name} (Facebook Messenger)"
    ])

    return "\n".join(lines)


class MessengerDispatcher:
    """
    Quản lý kết nối và gửi tin nhắn Facebook Messenger qua cookie (fbchat-muqit).
    Chia sẻ worker thread và event loop Selector an toàn trên mọi hệ điều hành.
    """

    _global_loop = None
    _global_thread = None
    _global_lock = threading.Lock()

    def __init__(self, config_file=DEFAULT_CONFIG_PATH, db_file=None):
        self.config_file = config_file
        self.db_file = db_file
        self.client = None
        self._cookies_file = os.path.join(os.path.dirname(os.path.abspath(config_file)), "fb_cookies.json")
        self.load_config()

    @classmethod
    def _ensure_event_loop(cls):
        """Khởi động worker thread chạy event loop asyncio Selector toàn cục."""
        with cls._global_lock:
            if cls._global_loop is None or cls._global_loop.is_closed() or not (cls._global_thread and cls._global_thread.is_alive()):
                if sys.platform == "win32":
                    try:
                        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
                    except Exception:
                        pass
                cls._global_loop = asyncio.new_event_loop()
                cls._global_thread = threading.Thread(target=cls._global_loop.run_forever, daemon=True)
                cls._global_thread.start()
        return cls._global_loop

    def _run_coro(self, coro, timeout=30):
        loop = self._ensure_event_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=timeout)

    def load_config(self):
        with open(self.config_file, "r", encoding="utf-8") as f:
            self.full_cfg = json.load(f)
            self.messenger_cfg = self.full_cfg.get("messenger", {})
            self.bot_name = self.full_cfg.get("bot_name", "Yuki Bot")

    def _write_cookies_file(self, cookies_data):
        clean_cookies = []
        if isinstance(cookies_data, list):
            clean_cookies = cookies_data
        elif isinstance(cookies_data, dict):
            for k, v in cookies_data.items():
                clean_cookies.append({
                    "name": k,
                    "value": str(v),
                    "domain": ".facebook.com",
                    "path": "/"
                })

        with open(self._cookies_file, "w", encoding="utf-8") as f:
            json.dump(clean_cookies, f, ensure_ascii=False, indent=2)

    def connect(self) -> bool:
        """Kết nối tới Facebook Messenger bằng cookie và mở MQTT listener."""
        self.load_config()
        cookies = self.messenger_cfg.get("cookies")
        if not cookies:
            try:
                database.set_bot_status("messenger_cookie_status", "missing", db_file=self.db_file)
            except Exception:
                pass
            return False

        try:
            from fbchat_muqit import Client
        except ImportError:
            print(f"❌ [{self.bot_name}] [Messenger] Chưa cài thư viện fbchat-muqit.")
            return False

        try:
            print(f"🔄 [{self.bot_name}] [Messenger] Đang kết nối tới Facebook Messenger...")
            self._write_cookies_file(cookies)

            async def _do_connect():
                client = Client(cookies_file_path=self._cookies_file, disable_logs=True)
                await client.start()
                await client.start_listening()
                await asyncio.sleep(2)
                return client

            self.client = self._run_coro(_do_connect(), timeout=35)
            uid = getattr(self.client, 'uid', 'unknown')
            print(f"✅ [{self.bot_name}] [Messenger] Đăng nhập Facebook thành công! UID: {uid}")

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
            print(f"❌ [{self.bot_name}] [Messenger] Lỗi kết nối Facebook: {err_msg}")
            try:
                database.set_bot_status("messenger_cookie_status", "expired", db_file=self.db_file)
                database.set_bot_status("messenger_cookie_error", err_msg, db_file=self.db_file)
            except Exception:
                pass
            self.client = None
            return False

    def send_post_alert(self, post_data: dict, page_name: str, matched_kw: str = "", db_file=None) -> bool:
        """Gửi thông báo bài viết mạng xã hội (Bot 1 HUIT, Bot 2 VAA)."""
        self.load_config()
        if not self.messenger_cfg.get("enabled", False):
            return False

        target_list = [t for t in self.messenger_cfg.get("target_groups", []) if t.get("enabled")]
        if not target_list:
            return False

        if not self.client:
            if not self.connect():
                return False

        formatted_msg = format_post_messenger_message(post_data, page_name, bot_name=self.bot_name)
        ident = post_data.get("post_id") or post_data.get("id") or str(int(time.time()))
        post_url = post_data.get("post_url", "")
        post_title = extract_post_title(post_data.get("content", ""))

        any_success = False
        target_db = db_file or self.db_file

        for target in target_list:
            tid = str(target.get("id"))
            tname = target.get("name", tid)

            msg_target_id = f"MSG_{tid}"
            try:
                if database.is_activity_already_sent_zalo(ident, title=post_title, target_id=msg_target_id, db_file=target_db):
                    continue
            except Exception:
                pass

            try:
                async def _send(t_id=tid, text=formatted_msg):
                    return await self.client.send_message(text=text, thread_id=t_id)

                mid = self._run_coro(_send(), timeout=25)
                log_str = f"[{self.bot_name}] [Messenger] Đã gửi thông báo tới nhóm [{tname}] (ID: {tid}, MID: {mid})"
                print(f"📨 [Messenger] {log_str}")
                database.log_event("MESSENGER", log_str, db_file=target_db)

                try:
                    database.record_delivery(
                        post_id=ident,
                        post_title=post_title,
                        source_page=page_name,
                        author=page_name,
                        post_url=post_url,
                        content_snippet=formatted_msg[:3000],
                        has_form=1 if extract_form_links(post_data.get("content", "")) else 0,
                        matched_keyword=matched_kw or "Messenger",
                        zalo_target_id=msg_target_id,
                        zalo_target_name=f"[FB] {tname}",
                        target_type="MESSENGER_GROUP",
                        status="SUCCESS",
                        crawled_at=database.get_vn_now_str(),
                        db_file=target_db
                    )
                except Exception:
                    pass
                any_success = True

            except Exception as e:
                err_str = f"[{self.bot_name}] [Messenger] Lỗi gửi bài tới {tname} ({tid}): {e}"
                print(f"❌ {err_str}")
                database.log_event("ERROR", err_str, db_file=target_db)

        return any_success

    def send_activity_alert(self, act: dict, is_reopened: bool = False, db_file=None, unit_label: str = "Đơn vị") -> bool:
        """Gửi thông báo hoạt động sự kiện / ĐRL (Bot 3 IUH, Bot 4 UFM)."""
        self.load_config()
        if not self.messenger_cfg.get("enabled", False):
            return False

        target_list = [t for t in self.messenger_cfg.get("target_groups", []) if t.get("enabled")]
        if not target_list:
            return False

        if not self.client:
            if not self.connect():
                return False

        formatted_msg = format_activity_messenger_message(act, is_reopened=is_reopened, bot_name=self.bot_name, unit_label=unit_label)
        aid = str(act.get("activity_id", ""))
        title = act.get("title", "")
        target_db = db_file or self.db_file
        any_success = False

        for target in target_list:
            tid = str(target.get("id"))
            tname = target.get("name", tid)

            msg_target_id = f"MSG_{tid}"
            try:
                if database.is_activity_already_sent_zalo(aid, title=title, target_id=msg_target_id, db_file=target_db):
                    continue
            except Exception:
                pass

            try:
                async def _send(t_id=tid, text=formatted_msg):
                    return await self.client.send_message(text=text, thread_id=t_id)

                mid = self._run_coro(_send(), timeout=25)
                log_str = f"[{self.bot_name}] [Messenger] Đã gửi thông báo tới nhóm [{tname}] (ID: {tid}, MID: {mid})"
                print(f"📨 [Messenger] {log_str}")
                database.log_event("MESSENGER", log_str, db_file=target_db)

                try:
                    database.record_delivery(
                        post_id=aid,
                        post_title=title,
                        source_page=act.get("source", "Portal"),
                        author=act.get("unit") or act.get("organizer") or self.bot_name,
                        post_url=act.get("register_url") or act.get("url") or act.get("detail_url", ""),
                        content_snippet=formatted_msg[:3000],
                        has_form=1,
                        matched_keyword=f"+{act.get('points', 0)} ĐRL",
                        zalo_target_id=msg_target_id,
                        zalo_target_name=f"[FB] {tname}",
                        target_type="MESSENGER_GROUP",
                        status="SUCCESS",
                        crawled_at=database.get_vn_now_str(),
                        db_file=target_db
                    )
                except Exception:
                    pass
                any_success = True

            except Exception as e:
                err_str = f"[{self.bot_name}] [Messenger] Lỗi gửi tin tới {tname} ({tid}): {e}"
                print(f"❌ {err_str}")
                database.log_event("ERROR", err_str, db_file=target_db)

        return any_success

    def send_test_message(self, target_thread_id=None, db_file=None) -> tuple:
        """Gửi tin nhắn thử nghiệm tới nhóm Messenger."""
        if not self.client:
            if not self.connect():
                return False, "Không thể kết nối tới Facebook Messenger (Cookie đã hết hạn hoặc chưa nạp)"

        target_id = target_thread_id
        if not target_id:
            self.load_config()
            groups = self.messenger_cfg.get("target_groups", [])
            enabled_groups = [g for g in groups if g.get("enabled")]
            if not enabled_groups:
                return False, "Chưa có nhóm Messenger nào đang BẬT."
            target_id = str(enabled_groups[0]["id"])

        test_msg = (
            f"⚡ [{self.bot_name} - THỬ NGHIỆM FACEBOOK MESSENGER] ⚡\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 Nhóm nhận tin: {target_id}\n"
            f"⏰ Thời gian: {database.get_vn_now_str()}\n"
            "✅ Kết nối kênh Facebook Messenger thành công và đang hoạt động hoàn hảo!\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 {self.bot_name} (Facebook Messenger)"
        )

        try:
            async def _send():
                return await self.client.send_message(text=test_msg, thread_id=str(target_id))

            mid = self._run_coro(_send(), timeout=25)
            log_str = f"[{self.bot_name}] [Messenger] Đã gửi tin thử nghiệm tới nhóm {target_id} (MID: {mid})"
            database.log_event("TEST", log_str, db_file=db_file or self.db_file)
            return True, f"Đã gửi tin thử nghiệm Messenger thành công tới nhóm {target_id}!"
        except Exception as e:
            return False, f"[{self.bot_name}] [Messenger] Lỗi gửi tin thử nghiệm: {e}"

    def fetch_all_groups(self) -> list:
        """Lấy danh sách các nhóm chat gần nhất từ Messenger."""
        if not self.client:
            if not self.connect():
                return []

        try:
            async def _fetch():
                threads = await self.client.fetch_thread_list(limit=40)
                group_list = []
                for thread in threads:
                    t_type = getattr(thread, 'type', None)
                    t_name = getattr(thread, 'name', None) or ""
                    t_id = getattr(thread, 'id', None)

                    is_group = False
                    if t_type is not None:
                        t_type_str = str(t_type).lower()
                        if "group" in t_type_str:
                            is_group = True
                    if not is_group and t_name and hasattr(thread, 'participants') and len(thread.participants or []) > 2:
                        is_group = True

                    if t_id and (is_group or t_name):
                        group_list.append({
                            "id": str(t_id),
                            "name": t_name or f"Nhóm Messenger {t_id}",
                            "is_group": is_group
                        })
                return group_list

            return self._run_coro(_fetch(), timeout=25)

        except Exception as e:
            print(f"❌ [Messenger] Lỗi lấy danh sách nhóm: {e}")
            return []
