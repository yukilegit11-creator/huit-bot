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
from zlapi.models import Message, Mention, ThreadType
import re

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

class ZaloDispatcher:
    def __init__(self, config_file=CONFIG_PATH):
        self.config_file = config_file
        self.client = None
        self.load_config()

    def load_config(self):
        with open(self.config_file, "r", encoding="utf-8") as f:
            self.full_cfg = json.load(f)
            self.zalo_cfg = self.full_cfg.get("zalo", {})
            self.bot_name = self.full_cfg.get("bot_name") or ("Yuki 2 (VAA)" if "bot2" in str(self.config_file) else "Yuki 1 (HUIT)")

    def connect(self):
        self.load_config()
        cookies = self.zalo_cfg.get("cookies")
        imei = self.zalo_cfg.get("imei")
        if not cookies or not imei:
            print("⚠️ Chưa có cookies hoặc imei Zalo trong config.json")
            return False

        try:
            print("🔄 Đang kết nối tới Zalo Web...")
            try:
                self.client = ZaloAPI(phone="", password="", imei=imei, cookies=cookies)
            except TypeError:
                self.client = ZaloAPI(phone="", password="", imei=imei, session_cookies=cookies)
            
            uid = self.client.uid() if callable(self.client.uid) else self.client.uid
            print(f"✅ Đăng nhập Zalo Bot thành công! UID: {uid}")
            return True
        except Exception as e:
            print(f"❌ Lỗi kết nối Zalo: {e}")
            self.client = None
            return False

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

    def send_alert(self, post_data: dict, page_name: str, target_thread_id: str = None) -> bool:
        if not self.client:
            if not self.connect():
                return False

        self.load_config()
        # Xác định danh sách các nhóm đích
        target_list = []
        if target_thread_id:
            target_list = [{"id": str(target_thread_id), "name": "Mục chỉ định"}]
        else:
            configured_groups = self.zalo_cfg.get("target_groups", [])
            enabled_groups = [g for g in configured_groups if g.get("enabled")]
            if enabled_groups:
                target_list = enabled_groups
            else:
                fallback_id = str(self.zalo_cfg.get("target_thread_id", ""))
                if fallback_id:
                    target_list = [{
                        "id": fallback_id,
                        "name": self.zalo_cfg.get("target_group_name", "Mục mặc định")
                    }]

        if not target_list:
            print("⚠️ Chưa có nhóm Zalo nào được kích hoạt để gửi tin!")
            return False

        formatted_text, form_links = self.format_message(post_data, page_name)
        target_type_str = self.zalo_cfg.get("target_type", "GROUP").upper()
        thread_type = ThreadType.GROUP if target_type_str == "GROUP" else ThreadType.USER

        # Chuẩn bị Message với @All mention nếu gửi vào Group và auto_tag_all = True
        auto_tag = self.zalo_cfg.get("auto_tag_all", True)
        if thread_type == ThreadType.GROUP and auto_tag:
            mention = Mention(uid="-1", length=len("@All"), offset=0)
            msg_obj = Message(text=formatted_text, mention=mention)
        else:
            msg_obj = Message(text=formatted_text)

        any_success = False
        for g in target_list:
            gid = str(g["id"])
            gname = g.get("name", gid)
            for attempt in range(2):
                try:
                    res = self.client.send(
                        msg_obj,
                        thread_id=gid,
                        thread_type=thread_type
                    )
                    bot_label = getattr(self, "bot_name", "Yuki 1 (HUIT)")
                    form_info = f" (Kèm {len(form_links)} link form GG Doc)" if form_links else ""
                    print(f"📨 [Zalo] [{bot_label}] Bắn tin thành công vào nhóm [{gname}] (ID: {gid}){form_info}")
                    try:
                        import database
                        db_target = "bot2.db" if "bot2" in str(self.config_file) else None
                        database.log_event("ZALO", f"[{bot_label}] Đã gửi bài của [{page_name}] vào nhóm [{gname}]{form_info}", db_file=db_target)
                    except Exception:
                        pass
                    any_success = True
                    break
                except Exception as e:
                    print(f"⚠️ Thử gửi nhóm {gname} lần {attempt+1} thất bại: {e}")
                    time.sleep(2)
                    self.connect()
            time.sleep(1.5)

        return any_success


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    dispatcher = ZaloDispatcher()
    if dispatcher.connect():
        print("Tải danh sách nhóm...")
        for g in dispatcher.get_groups():
            print(f"- {g['name']} (ID: {g['id']})")
