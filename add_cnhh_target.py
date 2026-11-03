import json
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

p = r'c:\Users\Admin\Documents\HUIT\config.json'
with open(p, 'r', encoding='utf-8') as f:
    cfg = json.load(f)

targets = cfg.get("targets", [])

new_target = {
    "name": "LCĐ Khoa Công Nghệ Hóa Học - HUIT",
    "url": "https://www.facebook.com/cnhh.hufi",
    "enabled": True
}

exists = any("cnhh.hufi" in t.get("url", "").lower() for t in targets)
if not exists:
    targets.append(new_target)
    cfg["targets"] = targets
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f"Đã thêm 'LCĐ Khoa Công Nghệ Hóa Học - HUIT' vào config.json! Tổng số trang: {len(targets)}")
else:
    print("Trang đã tồn tại trong danh sách cào!")
