import os
import sys
import re
import json

sys.stdout.reconfigure(encoding='utf-8')
ROOT_DIR = r"C:\Users\Admin\Documents\HUIT"

print("--- Step 1: Patching ufm_scraper.py ---")
# Patch ufm_scraper.py in ROOT_DIR and vaa/ufm/
new_dangky_func = '''    def fetch_dangky_activities(self) -> tuple:
        """
        Bóc tách các hoạt động trên trang https://hoatdong.ufm.edu.vn/DangKy
        Nơi sinh viên đăng ký tham gia các hoạt động trực tiếp.
        """
        if not self.ensure_authenticated():
            return False, "Phiên đăng nhập UFM không hợp lệ", []

        try:
            r = self.session.get(self.DANGKY_URL, verify=False, timeout=20)
            if r.status_code != 200:
                return False, f"Mã trạng thái HTTP {r.status_code}", []

            soup = BeautifulSoup(r.text, "html.parser")
            activities = []

            for h5 in soup.find_all("h5"):
                full_title = h5.get_text(separator=" ", strip=True)
                if not full_title:
                    continue

                id_m = re.search(r"\\[ID\\s*(\\d+)\\]", full_title, re.IGNORECASE)
                a_tag = h5.find("a")
                detail_path = a_tag.get("href", "") if a_tag else ""

                if id_m:
                    raw_id = id_m.group(1).strip()
                    clean_title = re.sub(r"\\[ID\\s*\\d+\\]\\s*", "", full_title).strip()
                elif "Details/" in detail_path:
                    m2 = re.search(r"Details/([a-zA-Z0-9_-]+)", detail_path)
                    raw_id = m2.group(1) if m2 else full_title[:20]
                    clean_title = full_title
                else:
                    continue

                activity_id = f"UFM_{raw_id}"
                detail_url = f"{self.BASE_URL}{detail_path}" if detail_path.startswith("/") else (detail_path or self.DANGKY_URL)

                container = h5.find_parent("div", class_="p-5") or h5.find_parent("div")
                card = container.parent if container else h5.parent

                unit = "Chưa rõ đơn vị"
                event_time = "Chưa rõ thời gian"
                location = "Chưa rõ địa điểm"
                group_criteria = ""
                points = 0.0
                ctxh = 0.0

                if container:
                    for p in container.find_all("p"):
                        txt = p.get_text(separator=" ", strip=True)
                        parts = txt.split("|") if "|" in txt else [txt]
                        for part in parts:
                            part_clean = part.strip()
                            part_lower = part_clean.lower()
                            if "đơn vị:" in part_lower:
                                unit = part_clean.split(":", 1)[1].strip()
                            elif "thời gian:" in part_lower:
                                event_time = part_clean.split(":", 1)[1].strip()
                            elif "địa điểm:" in part_lower:
                                location = part_clean.split(":", 1)[1].strip()
                            elif "nhóm:" in part_lower:
                                group_criteria = part_clean.split(":", 1)[1].strip()
                        
                        pt_match = re.search(r"([\\d\\.]+)\\s*(?:đrl|điểm)", txt, re.IGNORECASE)
                        if pt_match:
                            try:
                                points = float(pt_match.group(1))
                            except Exception:
                                pass
                        ctxh_match = re.search(r"(\\d+)\\s*ctxh", txt, re.IGNORECASE)
                        if ctxh_match:
                            try:
                                ctxh = float(ctxh_match.group(1))
                            except Exception:
                                pass

                # Slot & Status extraction
                card_text = card.get_text(separator=" ", strip=True)
                slot_match = re.search(r"Số\\s*lượng\\s*:\\s*(\\d+\\s*/\\s*\\d+)", card_text, re.IGNORECASE)
                if not slot_match:
                    slot_match = re.search(r"(\\d+\\s*/\\s*\\d+)\\s*(?:\\(Đã đầy\\)|\\(Còn slot\\))", card_text, re.IGNORECASE)
                slots = slot_match.group(1).replace(" ", "") if slot_match else ""

                is_full = False
                status = "Đang mở đăng ký"
                if "hủy" in card_text.lower() and ("frm-cancel" in str(card) or "HuyDangKy" in str(card)):
                    status = f"Đã đăng ký" + (f" ({slots})" if slots else "")
                    is_full = False
                elif any(k in card_text.lower() for k in ["đã đủ số lượng", "đã đầy", "hết slot", "chưa mở", "kết thúc"]):
                    status = f"Đã đủ số lượng" + (f" ({slots})" if slots else "")
                    is_full = True
                elif "đăng ký" in card_text.lower():
                    status = f"Đang mở đăng ký" + (f" ({slots})" if slots else "")
                    is_full = False

                activities.append({
                    "activity_id": activity_id,
                    "raw_id": raw_id,
                    "title": clean_title,
                    "unit": unit,
                    "event_time": event_time,
                    "location": location,
                    "group_criteria": group_criteria,
                    "points": points,
                    "ctxh": ctxh,
                    "status": status,
                    "slots": slots,
                    "is_full": is_full,
                    "detail_url": detail_url,
                    "register_url": self.DANGKY_URL,
                    "source": "Trang Mở Đăng Ký UFM (/DangKy)"
                })

            return True, f"Bóc tách thành công {len(activities)} hoạt động đăng ký", activities

        except Exception as e:
            return False, f"Lỗi bóc tách /DangKy: {e}", []'''

for sp_path in [os.path.join(ROOT_DIR, "ufm_scraper.py"), os.path.join(ROOT_DIR, "vaa", "ufm", "ufm_scraper.py")]:
    if not os.path.exists(sp_path):
        continue
    with open(sp_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Replace def fetch_dangky_activities up to return False, f"Lỗi bóc tách /DangKy: {e}", []
    p_start = content.find("def fetch_dangky_activities(self)")
    p_end = content.find("def fetch_semester_activities(self", p_start)
    if p_start != -1 and p_end != -1:
        content = content[:p_start] + new_dangky_func.strip() + "\n\n    " + content[p_end:]
        print(f"Patched fetch_dangky_activities in {sp_path}")

    # Also update semester activities activity_id to UFM_ prefix
    content = content.replace('"activity_id": f"SEM_{raw_id_str}"', '"activity_id": f"UFM_{raw_id_str}"')
    
    with open(sp_path, "w", encoding="utf-8") as f:
        f.write(content)

print("ufm_scraper.py updated successfully!")
