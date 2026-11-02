import os
import sys
import json
import time
from datetime import datetime, timezone, timedelta

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from zlapi import ZaloAPI
from zlapi.models import Message, Mention, ThreadType
import database

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def format_ufm_message(act: dict, is_reopened: bool = False, auto_tag_all: bool = True, bot_name: str = "Yuki 4 (UFM)") -> str:
    tag_str = "@All\n" if auto_tag_all else ""
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
        f"{tag_str}{header}",
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
        f"🤖 {bot_name}"
    ])

    return "\n".join(lines)


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
            self.bot_name = self.full_cfg.get("bot_name", "Yuki 4 (UFM)")

    def connect(self) -> bool:
        self.load_config()
        cookies = self.zalo_cfg.get("cookies")
        imei = self.zalo_cfg.get("imei")
        if not cookies or not imei:
            print("⚠️ Chưa có cookies hoặc imei Zalo trong config.json")
            return False

        cls = self.client_class or ZaloAPI
        try:
            print("🔄 Đang kết nối tới Zalo Bot UFM...")
            try:
                self.client = cls(phone="", password="", imei=imei, cookies=cookies)
            except TypeError:
                self.client = cls(phone="", password="", imei=imei, session_cookies=cookies)

            if hasattr(self.client, "db_file") and self.db_file:
                self.client.db_file = self.db_file
            if hasattr(self.client, "bot_name") and self.bot_name:
                self.client.bot_name = self.bot_name

            uid = self.client.uid() if callable(self.client.uid) else self.client.uid
            print(f"✅ Đăng nhập Zalo Bot UFM thành công! UID: {uid}")
            return True
        except Exception as e:
            print(f"❌ Lỗi kết nối Zalo UFM: {e}")
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

    def send_activity_alert(self, act: dict, is_reopened: bool = False, db_file=None) -> bool:
        self.load_config()
        configured_groups = self.zalo_cfg.get("target_groups")
        if configured_groups is not None:
            target_list = [t for t in configured_groups if t.get("enabled") is True or str(t.get("enabled", "")).lower() in ("true", "1")]
            if not target_list:
                print("⏸️ [UFM] Tất cả nhóm Zalo nhận tin đều đang ở trạng thái TẮT. Không gửi thông báo.")
                return False
        else:
            fallback_id = self.zalo_cfg.get("target_thread_id")
            target_list = [{"id": fallback_id, "name": self.zalo_cfg.get("target_group_name", "demo"), "type": self.zalo_cfg.get("target_type", "GROUP"), "enabled": True}] if fallback_id else []

        if not target_list:
            return False

        if not self.client:
            if not self.connect():
                return False

        auto_tag_all = self.zalo_cfg.get("auto_tag_all", True)
        formatted_msg = format_ufm_message(act, is_reopened=is_reopened, auto_tag_all=auto_tag_all, bot_name=self.bot_name)
        any_success = False

        for target in target_list:
            tid = str(target.get("id"))
            tname = target.get("name", tid)
            is_user = str(target.get("type", "GROUP")).upper() == "USER"
            t_type = ThreadType.USER if is_user else ThreadType.GROUP

            if is_user:
                clean_text = formatted_msg
                if clean_text.startswith("@All\n"):
                    clean_text = clean_text[5:]
                elif clean_text.startswith("@All "):
                    clean_text = clean_text[5:]
                msg_obj = Message(text=clean_text)
            else:
                if auto_tag_all and formatted_msg.startswith("@All"):
                    mention = Mention(uid="-1", length=len("@All"), offset=0)
                    msg_obj = Message(text=formatted_msg, mention=mention)
                else:
                    clean_text = formatted_msg[5:] if formatted_msg.startswith("@All\n") else formatted_msg
                    msg_obj = Message(text=clean_text)

            # Kiểm tra chống gửi trùng lặp tuyệt đối
            if database.is_activity_already_sent_zalo(str(act.get("activity_id", "")), title=act.get("title"), target_id=tid, db_file=db_file):
                print(f"🛑 [Chống lặp UFM] Hoạt động [{act.get('title')}] đã được gửi tới {tname} ({tid}) trước đó, bỏ qua!")
                continue

            try:
                self.client.send(msg_obj, thread_id=tid, thread_type=t_type)
                kind_str = "cá nhân" if is_user else "nhóm"
                log_str = f"[{self.bot_name}] Đã gửi thông báo tới {kind_str} [{tname}] (ID: {tid})"
                print(f"📨 [Zalo] {log_str}")
                database.log_event("ZALO", log_str, db_file=db_file)
                database.record_delivery(
                    post_id=act.get("activity_id", ""),
                    post_title=act.get("title", ""),
                    source_page=act.get("source", "UFM Portal"),
                    author=act.get("unit", "UFM"),
                    post_url=act.get("detail_url", "https://hoatdong.ufm.edu.vn/DangKy"),
                    content_snippet=clean_text[:3000],
                    has_form=1,
                    matched_keyword=f"+{act.get('points', 0)} ĐRL",
                    zalo_target_id=tid,
                    zalo_target_name=tname,
                    target_type=target.get("type", "GROUP"),
                    status="SUCCESS",
                    crawled_at=database.get_vn_now_str(),
                    db_file=db_file
                )
                any_success = True
            except Exception as e:
                err_str = f"Lỗi gửi tin tới {tname} ({tid}): {e}"
                print(f"❌ [Zalo] {err_str}")
                database.log_event("ERROR", err_str, db_file=db_file)
                database.record_delivery(
                    post_id=act.get("activity_id", ""),
                    post_title=act.get("title", ""),
                    source_page=act.get("source", "UFM Portal"),
                    author=act.get("unit", "UFM"),
                    post_url=act.get("detail_url", "https://hoatdong.ufm.edu.vn/DangKy"),
                    content_snippet=str(err_str)[:1000],
                    has_form=1,
                    matched_keyword=f"+{act.get('points', 0)} ĐRL",
                    zalo_target_id=tid,
                    zalo_target_name=tname,
                    target_type=target.get("type", "GROUP"),
                    status="FAILED",
                    crawled_at=database.get_vn_now_str(),
                    db_file=db_file
                )

        return any_success

    def send_test_message(self, target_thread_id=None, db_file=None) -> tuple:
        if not self.client:
            if not self.connect():
                return False, "Không thể kết nối tới Zalo Web"

        test_act = {
            "activity_id": f"TEST_{int(time.time())}",
            "raw_id": "TEST",
            "title": "Hoạt động Thử Nghiệm Hệ Thống Bot UFM",
            "unit": "Phòng Công tác sinh viên - Đại học Tài chính - Marketing (UFM)",
            "event_time": database.get_vn_now_str(),
            "location": "Trường ĐH Tài chính - Marketing (Cơ sở Long Trường)",
            "group_criteria": "3.a.1 - Rèn luyện thể chất & kỹ năng sinh viên",
            "points": 5.0,
            "ctxh": 10.0,
            "status": "Đang mở đăng ký (Thử nghiệm)",
            "detail_url": "https://hoatdong.ufm.edu.vn/DangKy",
            "register_url": "https://hoatdong.ufm.edu.vn/DangKy",
            "source": "Thử nghiệm từ Web Dashboard UFM"
        }

        # Nếu có target_thread_id cụ thể:
        if target_thread_id:
            tid = str(target_thread_id)
            msg_text = format_ufm_message(test_act, is_reopened=False, auto_tag_all=False, bot_name=self.bot_name)
            try:
                self.client.send(Message(text=msg_text), thread_id=tid, thread_type=ThreadType.GROUP)
                database.log_event("TEST", f"Đã gửi tin thử nghiệm tới nhóm {tid}", db_file=db_file)
                return True, f"Đã gửi tin thử nghiệm thành công tới ID {tid}!"
            except Exception as e:
                return False, f"Lỗi gửi tin: {e}"

        res = self.send_activity_alert(test_act, db_file=db_file)
        if res:
            return True, "Đã gửi thông báo thử nghiệm thành công tới các nhóm Zalo đang bật!"
        return False, "Chưa gửi được tin thử nghiệm (kiểm tra lại danh sách nhóm Zalo hoặc trạng thái kết nối)"
