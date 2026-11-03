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

    now_vn = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S %d/%m/%Y")
    posted_time = act.get("posted_time") or act.get("first_seen") or now_vn

    points_str_list = []
    if points > 0:
        points_str_list.append(f"+{points:g} ĐRL")
    if ctxh > 0:
        points_str_list.append(f"+{ctxh:g} CTXH")
    
    if points_str_list:
        lines.append(f"🎯 Điểm: {' • '.join(points_str_list)}")

    lines.append(f"⏰ Thời gian đăng bài: {posted_time}")

    if event_time and event_time != "Chưa rõ thời gian":
        lines.append(f"📅 Thời gian diễn ra: {event_time}")

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

        # 2.5 Lệnh bắn thông báo thử nghiệm vào nhóm demo
        if lower_txt in ("/demo", "/testdemo", "bắn demo", "gửi demo", "demo alert", "/senddemo"):
            dispatcher = ZaloDispatcher(self.config_path, db_file=self.db_file)
            dispatcher.client = self
            dispatcher.bot_name = self.bot_name
            ok_demo, msg_demo = dispatcher.send_demo_group_alert(db_file=self.db_file)
            reply = f"🚀 [{self.bot_name}]\n{msg_demo}"
            try:
                self.send(Message(text=reply), thread_id=thread_id, thread_type=thread_type)
            except Exception:
                pass
            return

        # 2.6 Lệnh liệt kê danh sách nhóm nhận tin của bot
        if lower_txt in ("/listgroup", "/groups", "danh sách nhóm", "/dsnhom", "ds nhóm", "nhóm zalo"):
            cfg_data = getattr(self, "full_cfg", {})
            if not cfg_data:
                try:
                    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                        cfg_data = json.load(f)
                except Exception:
                    cfg_data = {}
            tgs = cfg_data.get("zalo", {}).get("target_groups", [])
            lines = [
                f"📋 [{self.bot_name} - DANH SÁCH MỤC TIÊU NHẬN TIN]",
                "━━━━━━━━━━━━━━━━━━━━"
            ]
            for i, g in enumerate(tgs):
                t_kind = "Nhóm" if g.get("type") == "GROUP" else "Cá nhân"
                en = "✅ Bật" if g.get("enabled", True) else "⏸️ Tắt"
                lines.append(f"{i+1}. {g.get('name')} ({t_kind}) - {en}")
                lines.append(f"   ID: {g.get('id')}")
            lines.extend([
                "━━━━━━━━━━━━━━━━━━━━",
                "💡 Cú pháp bắn tin test:",
                "👉 /test <tên nhóm hoặc ID> (Ví dụ: /test demo)",
                "👉 /testall (Bắn thử toàn bộ nhóm đang bật)",
                f"🤖 {self.bot_name}"
            ])
            try:
                self.send(Message(text="\n".join(lines)), thread_id=thread_id, thread_type=thread_type)
            except Exception:
                pass
            return

        # 2.7 Lệnh bắn thử toàn bộ nhóm đang bật
        if lower_txt in ("/testall", "test all", "test tất cả", "bắn test all"):
            cfg_data = getattr(self, "full_cfg", {})
            if not cfg_data:
                try:
                    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                        cfg_data = json.load(f)
                except Exception:
                    cfg_data = {}
            tgs = [g for g in cfg_data.get("zalo", {}).get("target_groups", []) if g.get("enabled", True)]
            dispatcher = ZaloDispatcher(db_file=self.db_file)
            dispatcher.client = self
            dispatcher.bot_name = self.bot_name
            succ, fail = 0, 0
            for g in tgs:
                ok, _ = dispatcher.send_test_message_to_target(
                    target_id=str(g["id"]),
                    target_type=g.get("type", "GROUP"),
                    db_file=self.db_file
                )
                if ok: succ += 1
                else: fail += 1
                time.sleep(1)
            reply = f"🚀 [{self.bot_name} - TEST TẤT CẢ]\nĐã gửi tin nhắn test tới {succ}/{len(tgs)} nhóm đang bật (Thất bại: {fail})."
            try:
                self.send(Message(text=reply), thread_id=thread_id, thread_type=thread_type)
            except Exception:
                pass
            return

        # 2.8 Lệnh bắn thử theo tên nhóm hoặc ID
        if lower_txt.startswith("/test ") or lower_txt.startswith("test "):
            target_query = lower_txt[6:].strip() if lower_txt.startswith("/test ") else lower_txt[5:].strip()
            cfg_data = getattr(self, "full_cfg", {})
            if not cfg_data:
                try:
                    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                        cfg_data = json.load(f)
                except Exception:
                    cfg_data = {}
            tgs = cfg_data.get("zalo", {}).get("target_groups", [])
            matched_tg = None
            for g in tgs:
                if target_query == str(g.get("id")) or target_query in g.get("name", "").lower():
                    matched_tg = g
                    break
            
            dispatcher = ZaloDispatcher(db_file=self.db_file)
            dispatcher.client = self
            dispatcher.bot_name = self.bot_name

            if matched_tg:
                ok, msg = dispatcher.send_test_message_to_target(
                    target_id=str(matched_tg["id"]),
                    target_type=matched_tg.get("type", "GROUP"),
                    db_file=self.db_file
                )
                reply = f"🚀 [{self.bot_name}]\n{msg}"
            else:
                if target_query.isdigit() and len(target_query) > 5:
                    ok, msg = dispatcher.send_test_message_to_target(
                        target_id=target_query,
                        target_type="GROUP",
                        db_file=self.db_file
                    )
                    reply = f"🚀 [{self.bot_name}]\n{msg}"
                else:
                    reply = f"⚠️ Không tìm thấy nhóm nào khớp với '{target_query}'.\nGõ /listgroup để xem danh sách nhóm!"

            try:
                self.send(Message(text=reply), thread_id=thread_id, thread_type=thread_type)
            except Exception:
                pass
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
            try:
                database.set_bot_status("zalo_cookie_status", "missing", db_file=self.db_file)
                database.set_bot_status("zalo_cookie_error", "Chưa có cookies hoặc IMEI trong config.json", db_file=self.db_file)
            except Exception:
                pass
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
            try:
                database.set_bot_status("zalo_cookie_status", "valid", db_file=self.db_file)
                database.set_bot_status("zalo_cookie_error", "", db_file=self.db_file)
                database.set_bot_status("zalo_account_uid", str(uid), db_file=self.db_file)
                database.set_bot_status("zalo_last_connected", database.get_vn_now_str(), db_file=self.db_file)
            except Exception:
                pass
            return True
        except Exception as e:
            err_msg = str(e)
            print(f"❌ Lỗi kết nối Zalo UFM: {err_msg}")
            try:
                database.set_bot_status("zalo_cookie_status", "expired", db_file=self.db_file)
                database.set_bot_status("zalo_cookie_error", err_msg, db_file=self.db_file)
                database.log_event("WARN", f"Cookie Zalo hết hạn hoặc bị hủy: {err_msg}", db_file=self.db_file)
            except Exception:
                pass
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
                err_lower = str(e).lower()
                if any(w in err_lower for w in ["session", "expire", "auth", "login", "cookie", "token", "unauthorized", "invalid", "1001", "1002", "logout", "logged out"]):
                    try:
                        database.set_bot_status("zalo_cookie_status", "expired", db_file=db_file)
                        database.set_bot_status("zalo_cookie_error", f"Phiên Zalo hết hạn hoặc bị hủy: {e}", db_file=db_file)
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
                return False, "Không thể kết nối tới Zalo Web (Cookie đã hết hạn hoặc bị hủy)"

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

        # Nếu không có target_thread_id cụ thể, CHỈ gửi thử nghiệm cho nhóm demo và Trần Lê Phát
        test_targets = [
            {"id": "7456361874031804652", "name": "demo", "type": ThreadType.GROUP},
            {"id": "7662918962461429024", "name": "Trần Lê Phát", "type": ThreadType.USER}
        ]
        any_succ = False
        for t in test_targets:
            msg_text = format_ufm_message(test_act, is_reopened=False, auto_tag_all=False, bot_name=self.bot_name)
            try:
                self.client.send(Message(text=msg_text), thread_id=t["id"], thread_type=t["type"])
                database.log_event("TEST", f"Đã gửi tin thử nghiệm tới {t['name']} ({t['id']})", db_file=db_file)
                any_succ = True
            except Exception as e:
                print(f"Lỗi gửi test tới {t['name']}: {e}")
        if any_succ:
            return True, "Đã gửi thông báo thử nghiệm thành công CHỈ cho riêng Trần Lê Phát & nhóm demo!"
        return False, "Chưa gửi được tin thử nghiệm tới nhóm demo hoặc Trần Lê Phát."

    def send_demo_group_alert(self, custom_act=None, db_file=None) -> tuple:
        """Gửi thông báo sự kiện / hoạt động vào nhóm 'demo' (ID: 7456361874031804652)."""
        if not self.client:
            if not self.connect():
                return False, "Không thể kết nối Zalo Web! Vui lòng cập nhật Cookie Zalo trong cài đặt."

        demo_id = "7456361874031804652"
        now_vn = database.get_vn_now_str()

        # Tìm hoạt động mới nhất hoặc dùng hoạt động mẫu
        act = custom_act
        if not act:
            try:
                acts = database.get_crawled_activities(limit=1, db_file=db_file)
                if acts:
                    act = dict(acts[0])
            except Exception:
                pass

        if not act:
            act = {
                "activity_id": f"DEMO_{int(time.time())}",
                "raw_id": "DEMO",
                "title": "Hoạt động Thử Nghiệm Hệ Thống Bot UFM & Bắn Zalo",
                "unit": "Phòng Công tác sinh viên - Đại học Tài chính - Marketing (UFM)",
                "event_time": now_vn,
                "location": "Trường ĐH Tài chính - Marketing (Cơ sở Long Trường)",
                "group_criteria": "3.a.1 - Rèn luyện thể chất & kỹ năng sinh viên",
                "points": 5.0,
                "ctxh": 10.0,
                "status": "Đang mở đăng ký (Thử nghiệm)",
                "detail_url": "https://hoatdong.ufm.edu.vn/DangKy",
                "register_url": "https://hoatdong.ufm.edu.vn/DangKy",
                "source": "Thử nghiệm từ Web Dashboard UFM"
            }

        msg_text = format_ufm_message(act, is_reopened=False, auto_tag_all=True, bot_name=self.bot_name)
        mention = Mention(uid="-1", length=len("@All"), offset=0)
        msg_obj = Message(text=msg_text, mention=mention)

        try:
            self.client.send(msg_obj, thread_id=demo_id, thread_type=ThreadType.GROUP)
            log_str = f"[{self.bot_name}] Đã gửi thông báo thành công vào nhóm [demo] (ID: {demo_id})"
            print(f"📨 [Zalo] {log_str}")
            database.log_event("DEMO", log_str, db_file=db_file)
            database.record_delivery(
                post_id=str(act.get("activity_id", f"DEMO_{int(time.time())}")),
                post_title=act.get("title", "Demo Notification"),
                source_page="UFM Portal Demo",
                author=act.get("unit", "UFM"),
                post_url=act.get("register_url", "https://hoatdong.ufm.edu.vn/DangKy"),
                content_snippet=msg_text[:3000],
                has_form=1,
                matched_keyword=f"+{act.get('points', 5)} ĐRL",
                zalo_target_id=demo_id,
                zalo_target_name="demo",
                target_type="GROUP",
                status="SUCCESS",
                crawled_at=now_vn,
                db_file=db_file
            )
            return True, f"Đã gửi thông báo thành công vào nhóm demo (ID: {demo_id})!"
        except Exception as e:
            err_str = f"Lỗi gửi thông báo vào nhóm demo: {e}"
            print(f"❌ [Zalo] {err_str}")
            database.log_event("ERROR", err_str, db_file=db_file)
            return False, err_str

    def send_test_message_to_target(self, target_id: str, target_type: str = "GROUP", custom_text: str = None, db_file: str = None) -> tuple:
        """Gửi tin nhắn test tới một target_id cụ thể (GROUP hoặc USER) của bot."""
        if not self.client:
            if not self.connect():
                return False, "Không thể kết nối Zalo API!"

        now_vn = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S %d/%m/%Y")
        is_group = str(target_type).upper() == "GROUP"
        t_type = ThreadType.GROUP if is_group else ThreadType.USER

        if custom_text and custom_text.strip():
            msg_text = custom_text.strip()
        else:
            tag_str = "@All\n" if is_group else ""
            msg_text = (
                f"{tag_str}🧪 [KIỂM TRA TÍN HIỆU ZALO 24/7] 🧪\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 Bot phát tín hiệu: {self.bot_name}\n"
                f"🎯 Mục tiêu: {target_id} ({'Nhóm' if is_group else 'Cá nhân'})\n"
                f"⏰ Thời gian: {now_vn}\n"
                f"🌐 Máy chủ: VPS Cloud (180.93.125.40)\n"
                f"✅ Trạng thái kết nối: Hoạt động hoàn hảo 100%!\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🎯 Hệ thống đã sẵn sàng bắn thông báo tự động ngay khi có bài viết hoặc sự kiện mới."
            )

        if is_group:
            mention = Mention(uid="-1", length=len("@All"), offset=0)
            msg_obj = Message(text=msg_text, mention=mention)
        else:
            msg_obj = Message(text=msg_text)

        try:
            res = self.client.send(msg_obj, thread_id=str(target_id), thread_type=t_type)
            if hasattr(res, "error_code") and res.error_code not in (0, None):
                err_msg = getattr(res, "error_message", "Thất bại")
                return False, f"Zalo báo lỗi #{res.error_code}: {err_msg}"
            msg_id = getattr(res, "msgId", None) or getattr(res, "message_id", None)
            log_str = f"[{self.bot_name}] Đã gửi tin nhắn test thành công tới {target_id}!"
            print(f"📨 [Zalo Test] {log_str} (msgId: {msg_id})")
            db_t = db_file or getattr(self, "db_file", None) or database.DB_FILE
            try:
                database.log_event("TEST", log_str, db_file=db_t)
            except Exception:
                pass
            return True, f"Đã gửi tin nhắn test thành công tới {target_id} (Mã tin: {msg_id or 'OK'})!"
        except Exception as e:
            err_str = f"Lỗi gửi tin nhắn test tới {target_id}: {e}"
            print(f"❌ [Zalo Test] {err_str}")
            return False, err_str

