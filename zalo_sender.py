import json
import os
import sys
import time
from zlapi import ZaloAPI
from zlapi.models import Message, ThreadType

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

class ZaloDispatcher:
    def __init__(self, config_file=CONFIG_PATH):
        self.config_file = config_file
        self.client = None
        self.load_config()

    def load_config(self):
        with open(self.config_file, "r", encoding="utf-8") as f:
            self.full_cfg = json.load(f)
            self.zalo_cfg = self.full_cfg.get("zalo", {})

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

    def format_message(self, post_data: dict, page_name: str) -> str:
        author = post_data.get("author", "").strip() or "Thành viên nhóm"
        posted_time = post_data.get("posted_time", "").strip()
        text = post_data.get("content", "").strip()
        url = post_data.get("post_url", "").strip()

        header = f"📢 [THÔNG BÁO MỚI - {page_name.upper()}]"
        lines = [
            header,
            f"👤 Người đăng: {author}"
        ]
        if posted_time:
            lines.append(f"🕒 Thời gian: {posted_time}")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        
        # Cắt ngắn nếu bài quá dài (tối đa 450 ký tự)
        if len(text) > 450:
            lines.append(text[:450] + "...\n(Xem tiếp tại link bên dưới)")
        else:
            lines.append(text)
            
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        if url:
            lines.append(f"🔗 Link Facebook: {url}")
        lines.append("⚡ Cập nhật tự động 24/7 từ hệ thống HUIT Bot")

        return "\n".join(lines)

    def send_alert(self, post_data: dict, page_name: str, target_thread_id: str = None) -> bool:
        if not self.client:
            if not self.connect():
                return False

        thread_id = str(target_thread_id or self.zalo_cfg.get("target_thread_id", ""))
        if not thread_id:
            print("⚠️ Chưa có target_thread_id để gửi Zalo!")
            return False

        target_type_str = self.zalo_cfg.get("target_type", "GROUP").upper()
        thread_type = ThreadType.GROUP if target_type_str == "GROUP" else ThreadType.USER

        formatted_text = self.format_message(post_data, page_name)

        for attempt in range(2):
            try:
                res = self.client.send(
                    Message(text=formatted_text),
                    thread_id=thread_id,
                    thread_type=thread_type
                )
                print(f"📨 [Zalo] Bắn tin thành công vào thread {thread_id} ({page_name})")
                return True
            except Exception as e:
                print(f"⚠️ Thử lần {attempt+1} gửi Zalo thất bại: {e}")
                time.sleep(2)
                # Reconnect nếu lỗi phiên
                self.connect()

        return False

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    dispatcher = ZaloDispatcher()
    if dispatcher.connect():
        print("Tải danh sách nhóm...")
        for g in dispatcher.get_groups():
            print(f"- {g['name']} (ID: {g['id']})")
