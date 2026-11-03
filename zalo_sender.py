import json
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from zlapi import ZaloAPI
from zlapi import ZaloAPI
from zlapi.models import Message, Mention, ThreadType
import re
import hashlib
from datetime import datetime, timezone, timedelta

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

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

def parse_zalo_cookie_input(raw: str) -> dict:
    """Chuyển đổi chuỗi Cookie Zalo bất kỳ (JSON Array từ Cookie Editor, JSON Dict, hoặc Cookie Header) thành Dict chuẩn."""
    if not raw or not isinstance(raw, str):
        return {}
    raw_str = raw.strip()
    if not raw_str:
        return {}
    # 1. Thử JSON (Array hoặc Object)
    try:
        data = json.loads(raw_str)
        if isinstance(data, list):
            res = {}
            for item in data:
                if isinstance(item, dict) and "name" in item and "value" in item:
                    res[str(item["name"]).strip()] = str(item["value"]).strip()
            if res:
                return res
        elif isinstance(data, dict):
            return {str(k).strip(): str(v).strip() for k, v in data.items()}
    except Exception:
        pass

    # 2. Thử chuỗi key=val; key2=val2
    res = {}
    for part in raw_str.split(";"):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            if k.strip():
                res[k.strip()] = v.strip()
    return res

MAX_POST_AGE_MINUTES = 10.0

def is_post_fresh_within_10_minutes(post_data: dict) -> tuple:
    """
    CHỐT CHẶN TRUNG TÂM - Chỉ cho phép gửi Zalo khi đây là BÀI MỚI THẬT SỰ:
      - Phải có nội dung thật (không rỗng).
      - Phải có creation_time dạng số do Facebook trả về (không đoán, không giả lập).
      - Bài đăng cách hiện tại <= 10 phút.
    Ngoại lệ duy nhất: người dùng bấm nút "Gửi thử" trên Web (is_manual_test=True).
    Trả về (is_fresh: bool, reason: str)
    """
    if post_data.get("is_manual_test") is True:
        return True, "Tin thử nghiệm do người dùng bấm thủ công trên Web"

    if not str(post_data.get("content") or "").strip():
        return False, "Bài viết rỗng, không phải bài mới thật sự"

    c_time = post_data.get("creation_time")
    if isinstance(c_time, bool) or not isinstance(c_time, (int, float)) or c_time <= 0:
        return False, "Không có mốc thời gian đăng thật từ Facebook -> không xác minh được là bài mới"

    if c_time > 1e11:
        c_time = c_time / 1000.0
    age_minutes = (time.time() - c_time) / 60.0
    if age_minutes < -5.0:
        return False, f"Mốc thời gian bất thường (tương lai {abs(age_minutes):.1f} phút)"
    if age_minutes > MAX_POST_AGE_MINUTES:
        return False, f"Đã trôi qua {age_minutes:.1f} phút (> {MAX_POST_AGE_MINUTES:.0f} phút quy định)"
    return True, f"Mới đăng cách đây {max(age_minutes, 0):.1f} phút (<= {MAX_POST_AGE_MINUTES:.0f} phút)"

class UFMBotZaloClient(ZaloAPI):
    def __init__(self, *args, db_file=None, bot_name="Yuki 4 (UFM ĐRL)", **kwargs):
        super().__init__(*args, **kwargs)
        self.db_file = db_file
        self.bot_name = bot_name

    def onErrorCallBack(self, error):
        print(f"⚠️ [Zalo UFM Listener] {error}")

    def onMessage(self, mid=None, author_id=None, message=None, message_object=None, thread_id=None, thread_type=ThreadType.USER):
        my_uid = getattr(self, "uid", None)
        if callable(my_uid):
            my_uid = my_uid()
        if str(author_id) == str(my_uid):
            return

        text = ""
        if isinstance(message, str):
            text = message
        elif message_object and hasattr(message_object, "content"):
            text = str(message_object.content or "")
        elif message_object and hasattr(message_object, "msg"):
            text = str(message_object.msg or "")
        
        text = text.strip()
        if not text:
            return

        lower_txt = text.lower()
        # 1. Hướng dẫn nạp
        if lower_txt in ("/help", "/huongdan", "hướng dẫn", "huong dan", "/hd"):
            guide = (
                f"🎓 [{self.bot_name} - HƯỚNG DẪN NẠP TÀI KHOẢN SINH VIÊN]\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Bạn có thể gửi thông tin sinh viên theo một trong các định dạng sau:\n\n"
                "1️⃣ Định dạng 1 dòng (Dễ nhất):\n"
                "MSSV | Mật khẩu | Họ và tên\n"
                "👉 Ví dụ: 2621008460 | focusoncareer2111!!! | Đàm Anh Duy\n\n"
                "2️⃣ Định dạng nhiều dòng:\n"
                "MSSV: 2621008460\n"
                "Pass: focusoncareer2111!!!\n"
                "Tên: Đàm Anh Duy\n\n"
                "3️⃣ Nhắn trực tiếp MSSV và Mật khẩu:\n"
                "2621008460 focusoncareer2111!!!\n\n"
                "4️⃣ Nạp danh sách nhiều bạn (Mỗi bạn 1 dòng):\n"
                "2621008460 | pass1\n"
                "2621008461 | pass2\n\n"
                "💡 Hoặc tự nạp qua Web Dashboard tại mục 'Quản lý 100 Sinh viên'!\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 {self.bot_name} 24/7"
            )
            try:
                self.send(Message(text=guide), thread_id=thread_id, thread_type=thread_type)
            except Exception as e:
                print(f"❌ Lỗi gửi hướng dẫn: {e}")
            return

        # 2. Thống kê nhanh
        if lower_txt in ("/status", "/stats", "/dssv", "/check"):
            try:
                import database
                stats = database.get_student_stats(db_file=self.db_file)
                st_msg = (
                    f"📊 [{self.bot_name} - TRẠNG THÁI HỆ THỐNG]\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"👥 Tổng số sinh viên: {stats.get('total', 0)}\n"
                    f"🎯 Đang kích hoạt săn slot: {stats.get('active', 0)}\n"
                    f"🍪 Phiên Cookie hợp lệ: {stats.get('valid', 0)}\n"
                    f"🔐 Đã lưu mật khẩu (Auto-login): {stats.get('has_pass', 0)}\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "🚀 Hệ thống sẵn sàng tự động săn slot & bắn đăng ký ngay khi mở!"
                )
                self.send(Message(text=st_msg), thread_id=thread_id, thread_type=thread_type)
            except Exception as e:
                print(f"❌ Lỗi gửi thống kê: {e}")
            return

        # 3. Phân tích thông tin sinh viên
        try:
            import smart_parser
        except Exception:
            return

        students = smart_parser.parse_bulk_text(text)
        if not students:
            return

        if thread_type == ThreadType.GROUP:
            has_intent = (
                any(kw in lower_txt for kw in ["ufm", "mssv", "mật khẩu", "mat khau", "pass", "mk", "cookie", "drl", "đăng ký", "dang ky", "nạp", "nap"])
                or any(st.get("password") or st.get("cookie_data") for st in students)
                or "|" in text
                or lower_txt.startswith(("/napsv", "/sv", "/add"))
            )
            if not has_intent:
                return

        sender_name = "Sinh viên"
        try:
            u_info = self.fetchUserInfo(author_id)
            if u_info and hasattr(u_info, "changed_profiles") and author_id in u_info.changed_profiles:
                sender_name = u_info.changed_profiles[author_id].get("displayName", "Sinh viên")
            elif u_info and isinstance(u_info, dict) and "displayName" in u_info:
                sender_name = u_info.get("displayName", "Sinh viên")
        except Exception:
            pass

        print(f"📥 [Zalo Ingest] Nhận {len(students)} thông tin sinh viên từ {sender_name} ({author_id})")

        try:
            self.send(
                Message(text=f"⏳ [{self.bot_name}] Đang tiếp nhận & xác thực {len(students)} sinh viên trên cổng UFM... Vui lòng đợi trong giây lát!"),
                thread_id=thread_id,
                thread_type=thread_type
            )
        except Exception:
            pass

        import database
        res = smart_parser.bulk_enrich_and_save(
            raw_text=text,
            database_module=database,
            zalo_sender_id=str(author_id),
            zalo_sender_name=sender_name,
            db_file=self.db_file
        )

        items = res.get("items", [])
        succ_items = [it for it in items if it.get("status") == "success"]
        warn_items = [it for it in items if it.get("status") != "success"]

        lines = [
            f"🎓 [{self.bot_name} - TIẾP NHẬN SINH VIÊN] 🎓",
            "━━━━━━━━━━━━━━━━━━━━",
            f"👤 Người gửi: {sender_name}",
            f"📊 Kết quả: {len(succ_items)}/{len(items)} tài khoản hợp lệ",
            "━━━━━━━━━━━━━━━━━━━━"
        ]

        if succ_items:
            lines.append("✅ DANH SÁCH ĐÃ NẠP HỢP LỆ:")
            for it in succ_items:
                pass_label = "Đã lưu (Tự đăng nhập 24/7)" if it.get("has_password") else "Chưa có mật khẩu"
                cls_str = f" - Lớp: {it['class_name']}" if it.get("class_name") else ""
                lines.append(f"• MSSV: {it['mssv']} | {it['full_name']}{cls_str}")
                lines.append(f"  🔐 Mật khẩu: {pass_label} | Cookie: Hợp lệ")

        if warn_items:
            lines.append("\n⚠️ TÀI KHOẢN CẦN KIỂM TRA LẠI:")
            for it in warn_items:
                lines.append(f"• MSSV: {it['mssv']} - {it.get('message', 'Không xác thực được')}")

        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━",
            "🎯 Hệ thống đã ghi nhận và sẵn sàng tự động đăng ký khi có sự kiện/slot mới mở!",
            f"🤖 {self.bot_name}"
        ])

        reply_str = "\n".join(lines)
        try:
            self.send(Message(text=reply_str), thread_id=thread_id, thread_type=thread_type)
            print(f"✅ [Zalo Ingest] Đã phản hồi tới {thread_id}")
        except Exception as e:
            print(f"❌ [Zalo Ingest] Lỗi gửi phản hồi: {e}")


class ZaloDispatcher:
    def __init__(self, config_file=CONFIG_PATH, client_class=None, db_file=None):
        self.config_file = config_file
        self.client_class = client_class
        self.db_file = db_file
        self.client = None
        self.listener_thread = None
        self.load_config()

    def load_config(self):
        with open(self.config_file, "r", encoding="utf-8") as f:
            self.full_cfg = json.load(f)
            self.zalo_cfg = self.full_cfg.get("zalo", {})
            self.bot_name = self.full_cfg.get("bot_name") or ("Yuki 4 (UFM ĐRL)" if "ufm" in str(self.config_file).lower() else ("Yuki 2 (VAA)" if "bot2" in str(self.config_file) else "Yuki 1 (HUIT)"))

    def connect(self):
        self.load_config()
        cookies = self.zalo_cfg.get("cookies")
        imei = self.zalo_cfg.get("imei")
        if not cookies or not imei:
            print("⚠️ Chưa có cookies hoặc imei Zalo trong config.json")
            return False

        cls = self.client_class or ZaloAPI
        try:
            print("🔄 Đang kết nối tới Zalo Web...")
            try:
                self.client = cls(phone="", password="", imei=imei, cookies=cookies)
            except TypeError:
                self.client = cls(phone="", password="", imei=imei, session_cookies=cookies)
            
            if hasattr(self.client, "db_file") and self.db_file:
                self.client.db_file = self.db_file
            if hasattr(self.client, "bot_name") and self.bot_name:
                self.client.bot_name = self.bot_name

            uid = self.client.uid() if callable(self.client.uid) else self.client.uid
            print(f"✅ Đăng nhập Zalo Bot thành công! UID: {uid}")
            return True
        except Exception as e:
            print(f"❌ Lỗi kết nối Zalo: {e}")
            self.client = None
            return False

    def start_listener(self):
        if not self.client:
            return False
        if not hasattr(self.client, "listen"):
            return False

        def _listen_worker():
            try:
                print(f"🎧 [Zalo Listener] Bắt đầu lắng nghe tin nhắn Zalo cho {self.bot_name}...")
                self.client.listen(thread=True)
            except Exception as e:
                print(f"⚠️ [Zalo Listener] Tiến trình lắng nghe gặp lỗi: {e}")

        import threading
        self.listener_thread = threading.Thread(target=_listen_worker, daemon=True)
        self.listener_thread.start()
        return True

    def get_groups(self):
        if not self.client:
            if not self.connect():
                return []
        try:
            groups = self.client.fetchAllGroups()
            group_list = []
            if hasattr(groups, "gridVerMap"):
                for gid in groups.gridVerMap.keys():
                    info = self.client.fetchGroupInfo(gid)
                    gname = ""
                    if hasattr(info, "gridInfoMap") and gid in info.gridInfoMap:
                        gname = info.gridInfoMap[gid].get("name", "")
                    elif hasattr(info, "name"):
                        gname = info.name
                    group_list.append({"id": str(gid), "name": gname or "Nhóm không tên"})
            return group_list
        except Exception as e:
            print(f"⚠️ Lỗi lấy danh sách nhóm Zalo: {e}")
            return []

    def format_message(self, post_data: dict, page_name: str) -> tuple:
        posted_time = post_data.get("posted_time", "").strip() or "Vừa xong"
        text = post_data.get("content", "").strip()
        url = post_data.get("post_url", "").strip()
        title = extract_post_title(text)

        form_links = extract_form_links(text)
        tag_str = "@All " if self.zalo_cfg.get("auto_tag_all", True) else ""

        lines = []
        if form_links:
            # Khi phát hiện có link form: Ưu tiên nhấn mạnh vào form đăng ký sự kiện
            lines.append(f"{tag_str}🔥 [CÓ FORM ĐĂNG KÝ SỰ KIỆN] 🔥")
            lines.append(f"📰 Tiêu đề: {title}")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append("🎯 LINK FORM ĐĂNG KÝ SỰ KIỆN:")
            for flink in form_links:
                lines.append(f"👉 {flink}")
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append(f"📌 Tên nhóm đăng: {page_name}")
            lines.append(f"🕒 Thời gian đăng: {posted_time}")
        else:
            # Thông báo bài viết thường
            lines.append(f"{tag_str}📢 [THÔNG BÁO MỚI]")
            lines.append(f"📰 Tiêu đề: {title}")
            lines.append(f"📌 Tên nhóm đăng: {page_name}")
            lines.append(f"🕒 Thời gian đăng: {posted_time}")

        # Link bài viết
        if url:
            lines.append("━━━━━━━━━━━━━━━━━━━━")
            lines.append(f"🔗 Link bài viết: {url}")

        lines.append("━━━━━━━━━━━━━━━━━━━━")
        # Câu xin lỗi nếu làm phiền
        lines.append("🙏 Xin lỗi nếu thông báo này đã làm phiền các bạn!")
        bot_label = getattr(self, "bot_name", "Yuki 1 (HUIT)")
        lines.append(f"🤖 {bot_label}")

        formatted_text = "\n".join(lines)
        return formatted_text, form_links

    def send_alert(self, post_data: dict, page_name: str, target_thread_id: str = None, matched_kw: str = "") -> bool:
        # 0. CHỐT CHẶN: Cấm tự động gửi khi không phải bài mới thật sự
        is_fresh, fresh_reason = is_post_fresh_within_10_minutes(post_data)
        if not is_fresh:
            bot_label = getattr(self, "bot_name", "Yuki Bot")
            msg = f"⛔ [{bot_label}] CHẶN gửi Zalo: {fresh_reason}"
            print(msg)
            try:
                import database
                cfg_lower = str(self.config_file).lower()
                if "bot2" in cfg_lower or "vaa" in cfg_lower:
                    db_g = database.BOT2_DB_FILE
                elif "iuh" in cfg_lower:
                    db_g = database.IUH_DB_FILE
                else:
                    db_g = database.DB_FILE
                database.log_event("FILTER", msg, db_file=db_g)
            except Exception:
                pass
            return False

        if not self.client:
            if not self.connect():
                bot_label = getattr(self, "bot_name", "Yuki Bot")
                err_msg = f"❌ [{bot_label}] Kết nối Zalo thất bại (Cookie hết hạn hoặc phiên bị hủy). Bỏ qua gửi tin!"
                print(err_msg)
                try:
                    import database
                    cfg_lower = str(self.config_file).lower()
                    db_target = database.BOT2_DB_FILE if ("bot2" in cfg_lower or "vaa" in cfg_lower) else (database.IUH_DB_FILE if "iuh" in cfg_lower else database.DB_FILE)
                    database.log_event("ERROR", err_msg, db_file=db_target)
                except Exception:
                    pass
                return False

        self.load_config()
        # Xác định danh sách các nhóm đích
        target_list = []
        if target_thread_id:
            target_list = [{"id": str(target_thread_id), "name": "Mục chỉ định"}]
        else:
            configured_groups = self.zalo_cfg.get("target_groups")
            if configured_groups is not None:
                # Có danh sách nhóm được cấu hình: CHỈ gửi các nhóm có enabled rõ ràng là True
                enabled_groups = [
                    g for g in configured_groups
                    if g.get("enabled") is True or str(g.get("enabled", "")).lower() in ("true", "1")
                ]
                if not enabled_groups:
                    bot_label = getattr(self, "bot_name", "Yuki Bot")
                    warn_msg = f"⏸️ [{bot_label}] Tất cả các nhóm Zalo đều đang ở trạng thái TẮT. Bỏ qua gửi tin."
                    print(warn_msg)
                    try:
                        import database
                        cfg_lower = str(self.config_file).lower()
                        db_target = database.BOT2_DB_FILE if ("bot2" in cfg_lower or "vaa" in cfg_lower) else (database.IUH_DB_FILE if "iuh" in cfg_lower else database.DB_FILE)
                        database.log_event("FILTER", warn_msg, db_file=db_target)
                    except Exception:
                        pass
                    return False
                target_list = enabled_groups
            else:
                # Chỉ khi file cấu hình hoàn toàn không có target_groups (legacy)
                fallback_id = str(self.zalo_cfg.get("target_thread_id", ""))
                if fallback_id:
                    target_list = [{
                        "id": fallback_id,
                        "name": self.zalo_cfg.get("target_group_name", "Mục mặc định")
                    }]

        if not target_list:
            print("⚠️ Chưa có nhóm Zalo nào được kích hoạt để gửi tin!")
            return False

        # 1. Khử trùng lặp nhóm đích (chỉ gửi mỗi nhóm 1 lần duy nhất)
        seen_gids = set()
        clean_targets = []
        for g in target_list:
            gid = str(g.get("id")).strip()
            if gid not in seen_gids:
                seen_gids.add(gid)
                clean_targets.append(g)
        target_list = clean_targets

        # 2. Bộ nhớ đệm chống gửi trùng bài viết trong phiên chạy (tránh gửi 2 lần)
        if not hasattr(self, "_sent_cache"):
            self._sent_cache = {}
        now_ts = time.time()
        self._sent_cache = {k: v for k, v in self._sent_cache.items() if now_ts - v < 86400}

        pid = str(post_data.get("post_id", ""))
        content_key = post_data.get("content", "").strip()[:80]
        post_ident = f"{pid}_{content_key}"
        if post_ident in self._sent_cache:
            print(f"🛑 [Chống lặp tuyệt đối] Bài viết '{content_key[:30]}...' đã gửi trước đó trong phiên, nghiêm cấm gửi lần 2!")
            return True

        # 3. Kiểm tra trực tiếp cơ sở dữ liệu SQLite: Nghiêm cấm gửi lại bài đã gửi thành công
        cfg_lower = str(self.config_file).lower()
        try:
            import database
            if "bot2" in cfg_lower or "vaa" in cfg_lower:
                db_chk = database.BOT2_DB_FILE
            elif "iuh" in cfg_lower:
                db_chk = database.IUH_DB_FILE
            else:
                db_chk = database.DB_FILE

            if database.is_post_already_sent_zalo(pid, post_data.get("content", ""), db_file=db_chk):
                print(f"🛑 [Chống lặp tuyệt đối] Bài viết ID {pid} ('{content_key[:30]}...') đã được gửi thành công trước đó trong SQLite DB. Nghiêm cấm gửi lần 2!")
                self._sent_cache[post_ident] = now_ts
                return True
        except Exception as ex_db_chk:
            print(f"Lỗi kiểm tra trùng lặp DB: {ex_db_chk}")

        # 4. KIỂM TRA QUY ĐỊNH 10 PHÚT: Cấm gửi bài nếu đã đăng quá 10 phút hoặc không có thời gian thực sự
        is_fresh, fresh_reason = is_post_fresh_within_10_minutes(post_data)
        if not is_fresh:
            bot_label = getattr(self, "bot_name", "Yuki Bot")
            print(f"⏳ [{bot_label}] Bỏ qua không gửi Zalo: {fresh_reason} (Bài: '{content_key[:40]}...')")
            try:
                import database
                db_log = database.BOT2_DB_FILE if ("bot2" in cfg_lower or "vaa" in cfg_lower) else (database.IUH_DB_FILE if "iuh" in cfg_lower else database.DB_FILE)
                database.log_event("FILTER", f"⏳ Bỏ qua không gửi Zalo vì không phải bài mới thực sự trong 10 phút: {fresh_reason}", db_file=db_log)
            except Exception:
                pass
            return False

        formatted_text, form_links = self.format_message(post_data, page_name)
        target_type_str = self.zalo_cfg.get("target_type", "GROUP").upper()
        thread_type = ThreadType.GROUP if target_type_str == "GROUP" else ThreadType.USER

        any_success = False
        for g in target_list:
            gid = str(g["id"]).strip()
            gname = g.get("name", gid)

            # 4. Kiểm tra nhóm này đã từng nhận bài này chưa
            try:
                import database
                if "bot2" in cfg_lower or "vaa" in cfg_lower:
                    db_target = database.BOT2_DB_FILE
                elif "iuh" in cfg_lower:
                    db_target = database.IUH_DB_FILE
                else:
                    db_target = database.DB_FILE

                if database.is_post_already_sent_zalo(pid, post_data.get("content", ""), target_id=gid, db_file=db_target):
                    print(f"🛑 [Chống lặp nhóm] Bài viết đã từng gửi tới nhóm [{gname}] (ID: {gid}) trước đó, bỏ qua!")
                    continue
            except Exception:
                pass

            target_type = str(g.get("type") or self.zalo_cfg.get("target_type", "GROUP")).upper()
            is_user = (target_type == "USER")
            t_type = ThreadType.USER if is_user else ThreadType.GROUP

            # Nếu gửi cá nhân thì bỏ @All, nếu gửi nhóm và bật auto_tag thì đính kèm mention @All
            if is_user:
                clean_text = formatted_text
                if clean_text.startswith("@All "):
                    clean_text = clean_text[5:]
                msg_obj = Message(text=clean_text)
            else:
                auto_tag = self.zalo_cfg.get("auto_tag_all", True)
                if auto_tag and formatted_text.startswith("@All"):
                    mention = Mention(uid="-1", length=len("@All"), offset=0)
                    msg_obj = Message(text=formatted_text, mention=mention)
                else:
                    clean_text = formatted_text[5:] if formatted_text.startswith("@All ") else formatted_text
                    msg_obj = Message(text=clean_text)

            target_kind = "cá nhân" if is_user else "nhóm"
            try:
                res = self.client.send(
                    msg_obj,
                    thread_id=gid,
                    thread_type=t_type
                )
                bot_label = getattr(self, "bot_name", "Yuki 1 (HUIT)")
                form_info = f" (Kèm {len(form_links)} link form GG Doc)" if form_links else ""
                print(f"📨 [Zalo] [{bot_label}] Bắn tin thành công tới {target_kind} [{gname}] (ID: {gid}){form_info}")
                try:
                    import database
                    cfg_lower = str(self.config_file).lower()
                    if "bot2" in cfg_lower or "vaa" in cfg_lower:
                        db_target = database.BOT2_DB_FILE
                    elif "iuh" in cfg_lower:
                        db_target = database.IUH_DB_FILE
                    else:
                        db_target = database.DB_FILE
                    title = extract_post_title(post_data.get("content", ""))
                    database.record_delivery(
                        post_id=post_data.get("post_id") or hashlib.md5(post_data.get("content", "")[:150].encode("utf-8")).hexdigest(),
                        post_title=title,
                        source_page=page_name,
                        author=post_data.get("author", "Ẩn danh"),
                        post_url=post_data.get("post_url") or post_data.get("url", ""),
                        content_snippet=post_data.get("content", "")[:300],
                        has_form=1 if form_links else 0,
                        matched_keyword=matched_kw or "Mặc định",
                        zalo_target_id=gid,
                        zalo_target_name=gname,
                        target_type=target_type,
                        status="SUCCESS",
                        crawled_at=post_data.get("posted_time", ""),
                        db_file=db_target
                    )
                    database.log_event("ZALO", f"[{bot_label}] Đã gửi bài của [{page_name}] tới {target_kind} [{gname}]{form_info}", db_file=db_target)
                except Exception as ex_db:
                    print(f"Lỗi ghi DB: {ex_db}")
                any_success = True
            except Exception as e:
                print(f"⚠️ Lỗi gửi tin vào {target_kind} {gname}: {e}")
                try:
                    import database
                    cfg_lower = str(self.config_file).lower()
                    if "bot2" in cfg_lower or "vaa" in cfg_lower:
                        db_target = database.BOT2_DB_FILE
                    elif "iuh" in cfg_lower:
                        db_target = database.IUH_DB_FILE
                    else:
                        db_target = database.DB_FILE
                    title = extract_post_title(post_data.get("content", ""))
                    database.record_delivery(
                        post_id=post_data.get("post_id") or hashlib.md5(post_data.get("content", "")[:150].encode("utf-8")).hexdigest(),
                        post_title=title,
                        source_page=page_name,
                        author=post_data.get("author", "Ẩn danh"),
                        post_url=post_data.get("post_url") or post_data.get("url", ""),
                        content_snippet=post_data.get("content", "")[:300],
                        has_form=1 if form_links else 0,
                        matched_keyword=matched_kw or "Mặc định",
                        zalo_target_id=gid,
                        zalo_target_name=gname,
                        target_type=target_type,
                        status=f"FAILED: {e}",
                        crawled_at=post_data.get("posted_time", ""),
                        db_file=db_target
                    )
                except Exception:
                    pass
            time.sleep(1.0)

        if any_success:
            self._sent_cache[post_ident] = now_ts

        return any_success


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    dispatcher = ZaloDispatcher()
    if dispatcher.connect():
        print("Tải danh sách nhóm...")
        for g in dispatcher.get_groups():
            print(f"- {g['name']} (ID: {g['id']})")
