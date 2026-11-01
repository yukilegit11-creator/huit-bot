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

def is_post_fresh_within_10_minutes(post_data: dict) -> tuple:
    """
    So sánh thời gian đã đăng:
    Nếu đã trôi qua hơn 10 phút (> 600 giây) thì KHÔNG gửi thông báo vào Zalo.
    Trả về (is_fresh: bool, reason: str)
    """
    now_ts = time.time()
    c_time = post_data.get("creation_time")
    
    # 1. Kiểm tra timestamp UNIX creation_time
    if c_time and isinstance(c_time, (int, float)):
        if c_time > 1e11:
            c_time = c_time / 1000.0
        age_seconds = now_ts - c_time
        age_minutes = age_seconds / 60.0
        if age_minutes < -1.0:
            return True, f"Bài vừa đăng (lệch giờ nhẹ: {age_minutes:.1f}p)"
        if age_minutes > 10.0:
            return False, f"Đã trôi qua {age_minutes:.1f} phút (> 10 phút quy định)"
        return True, f"Mới đăng cách đây {age_minutes:.1f} phút (<= 10 phút)"

    # 2. Thử phân tích chuỗi posted_time
    posted_str = str(post_data.get("posted_time") or "").strip()
    if posted_str:
        for fmt in ("%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M"):
            try:
                dt = datetime.strptime(posted_str, fmt)
                dt_vn = dt.replace(tzinfo=timezone(timedelta(hours=7)))
                age_seconds = datetime.now(timezone(timedelta(hours=7))).timestamp() - dt_vn.timestamp()
                age_minutes = age_seconds / 60.0
                if age_minutes > 10.0:
                    return False, f"Đã trôi qua {age_minutes:.1f} phút (> 10 phút quy định từ '{posted_str}')"
                return True, f"Mới đăng cách đây {age_minutes:.1f} phút (<= 10 phút)"
            except Exception:
                continue

    # 3. Cho phép tin test thử nghiệm
    if post_data.get("is_test") or "KIỂM TRA" in post_data.get("content", ""):
        return True, "Bài viết thử nghiệm hệ thống"

    # 4. Không có mốc thời gian: KHÔNG GỬI để đảm bảo quy định 10 phút
    return False, "Không xác định được thời gian đăng chính xác để đảm bảo <= 10 phút"

MAX_POST_AGE_MINUTES = 10.0

def is_post_fresh_within_10_minutes(post_data: dict) -> tuple:
    """
    CHỐT CHẶN TRUNG TÂM - Chỉ cho phép gửi Zalo khi đây là BÀI MỚI THẬT SỰ:
      - Có nội dung thật, có creation_time dạng số từ Facebook, đăng <= 10 phút.
    Ngoại lệ duy nhất: người dùng bấm nút "Gửi thử" trên Web (is_manual_test=True).
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
    return True, f"Mới đăng cách đây {max(age_minutes, 0):.1f} phút"

def _already_sent(post_id: str, content: str, target_id: str = None, db_file=None) -> bool:
    """Kiểm tra delivery_history: bài đã gửi thành công (tới nhóm này) chưa."""
    try:
        conn = database.get_connection(db_file)
        cur = conn.cursor()
        q = "SELECT 1 FROM delivery_history WHERE status = 'SUCCESS' AND (post_id = ?"
        params = [str(post_id)]
        snippet = (content or "").strip()[:80]
        if len(snippet) >= 25:
            q += " OR content_snippet LIKE ?"
            params.append(f"%{snippet}%")
        q += ")"
        if target_id:
            q += " AND zalo_target_id = ?"
            params.append(str(target_id))
        cur.execute(q + " LIMIT 1", params)
        found = cur.fetchone() is not None
        conn.close()
        return found
    except Exception as e:
        print(f"Lỗi kiểm tra trùng lặp VAA: {e}")
        return False

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

    def send_alert(self, post_data: dict, page_name: str, target_thread_id: str = None, matched_kw: str = "") -> bool:
        if not self.client:
            if not self.connect():
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
                    print(f"⏸️ [{bot_label}] Tất cả các nhóm Zalo đều đang ở trạng thái TẮT (Disabled). Bỏ qua gửi tin bài này.")
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
