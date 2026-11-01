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
import hashlib

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vaabot.json")

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

import database

class ZaloDispatcher:
    def __init__(self, config_file=CONFIG_PATH):
        self.config_file = config_file
        self.client = None
        self.load_config()

    def load_config(self):
        with open(self.config_file, "r", encoding="utf-8") as f:
            self.full_cfg = json.load(f)
            self.zalo_cfg = self.full_cfg.get("zalo", {})
            self.bot_name = self.full_cfg.get("bot_name", "Yuki 2 (VAA)")

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
            print(f"✅ Đăng nhập Zalo Bot VAA thành công! UID: {uid}")
            return True
        except Exception as e:
            print(f"❌ Lỗi kết nối Zalo: {e}")
            self.client = None
            return False

    def format_alert_message(self, post_data: dict, page_name: str, is_user: bool = False) -> tuple:
        author = post_data.get("author", "Ẩn danh")
        content = post_data.get("content", "")
        post_url = post_data.get("post_url", "")
        posted_time = post_data.get("posted_time", "Vừa xong")

        form_links = extract_form_links(content)
        title = extract_post_title(content)

        clean_snippet = content.strip()
        if len(clean_snippet) > 280:
            clean_snippet = clean_snippet[:280].rsplit(" ", 1)[0] + "..."

        if form_links:
            header_line = "🔥 [CÓ FORM ĐĂNG KÝ SỰ KIỆN] 🔥" if is_user else "@All 🔥 [CÓ FORM ĐĂNG KÝ SỰ KIỆN] 🔥"
            form_block = "━━━━━━━━━━━━━━━━━━━━\n🎯 LINK FORM ĐĂNG KÝ SỰ KIỆN:\n"
            for fl in form_links:
                form_block += f"👉 {fl}\n"
            form_block += "━━━━━━━━━━━━━━━━━━━━"
        else:
            header_line = "📢 THÔNG BÁO HOẠT ĐỘNG MỚI" if is_user else "@All 📢 THÔNG BÁO HOẠT ĐỘNG MỚI"
            form_block = ""

        msg_parts = [
            header_line,
            f"📰 Tiêu đề: {title}"
        ]

        if form_block:
            msg_parts.append(form_block)

        msg_parts.extend([
            f"📌 Tên nhóm đăng: {page_name}",
            f"🕒 Thời gian đăng: {posted_time}",
            "━━━━━━━━━━━━━━━━━━━━",
            "📝 Tóm tắt nội dung:",
            clean_snippet,
            "━━━━━━━━━━━━━━━━━━━━",
            f"🔗 Link bài viết: {post_url}" if post_url else "",
            "\n(Nếu tin nhắn làm phiền, mình xin lỗi bạn nhiều nhé! 🙏)"
        ])

        final_text = "\n".join([p for p in msg_parts if p.strip()])
        return final_text, (not is_user and not form_links and self.zalo_cfg.get("auto_tag_all", True)) or (not is_user and bool(form_links))

    def send_alert(self, post_data: dict, page_name: str, matched_kw: str = "", db_file=None) -> bool:
        if not self.client:
            if not self.connect():
                print("❌ Không thể gửi Zalo vì chưa đăng nhập.")
                return False

        self.load_config()
        configured_groups = self.zalo_cfg.get("target_groups")
        if configured_groups is not None:
            active_targets = [
                g for g in configured_groups 
                if g.get("enabled") is True or str(g.get("enabled", "")).lower() in ("true", "1")
            ]
        else:
            thread_id = self.zalo_cfg.get("target_thread_id")
            thread_type_str = self.zalo_cfg.get("target_type", "GROUP")
            active_targets = [{"id": thread_id, "name": "Mặc định", "type": thread_type_str, "enabled": True}] if thread_id else []

        if not active_targets:
            print("⏸️ [VAA] Không có nhóm hoặc người nhận Zalo nào được BẬT (enabled: true). Bỏ qua gửi tin bài này.")
            return False

        # Khử trùng lặp ID người nhận/nhóm
        seen_gids = set()
        clean_targets = []
        for g in active_targets:
            gid = str(g.get("id")).strip()
            if gid not in seen_gids:
                seen_gids.add(gid)
                clean_targets.append(g)
        active_targets = clean_targets

        content = post_data.get("content", "")
        title = extract_post_title(content)
        form_links = extract_form_links(content)
        ident = post_data.get("post_id") or hashlib.md5(content[:150].encode("utf-8")).hexdigest()
        author = post_data.get("author", "Ẩn danh")
        post_url = post_data.get("post_url", "")
        crawled_at = post_data.get("posted_time", "")

        success_count = 0
        for target in active_targets:
            target_id = str(target.get("id"))
            target_name = target.get("name", "Người nhận")
            is_user = target.get("type") == "USER"
            target_type = ThreadType.USER if is_user else ThreadType.GROUP
            target_type_str = "USER" if is_user else "GROUP"

            msg_text, need_tag = self.format_alert_message(post_data, page_name, is_user=is_user)

            try:
                if need_tag and not is_user:
                    tag_len = len("@All")
                    mention = Mention(uid="-1", offset=0, length=tag_len)
                    msg_obj = Message(text=msg_text, mention=mention)
                else:
                    msg_obj = Message(text=msg_text)

                self.client.send(msg_obj, thread_id=target_id, thread_type=target_type)
                print(f"   🚀 Đã gửi thành công tới: {target_name} ({'Cá nhân' if is_user else 'Nhóm'}) [{target_id}]")
                success_count += 1

                # Ghi lịch sử bất biến không bao giờ xóa
                database.record_delivery(
                    post_id=ident,
                    post_title=title,
                    source_page=page_name,
                    author=author,
                    post_url=post_url,
                    content_snippet=content[:300],
                    has_form=1 if form_links else 0,
                    matched_keyword=matched_kw,
                    zalo_target_id=target_id,
                    zalo_target_name=target_name,
                    target_type=target_type_str,
                    status="SUCCESS",
                    crawled_at=crawled_at,
                    db_file=db_file
                )

                time.sleep(1.0)
            except Exception as e:
                print(f"   ❌ Lỗi gửi tin tới {target_name} ({target_id}): {e}")
                # Ghi nhận lỗi vào lịch sử
                database.record_delivery(
                    post_id=ident,
                    post_title=title,
                    source_page=page_name,
                    author=author,
                    post_url=post_url,
                    content_snippet=content[:300],
                    has_form=1 if form_links else 0,
                    matched_keyword=matched_kw,
                    zalo_target_id=target_id,
                    zalo_target_name=target_name,
                    target_type=target_type_str,
                    status=f"FAILED: {e}",
                    crawled_at=crawled_at,
                    db_file=db_file
                )

        return success_count > 0
