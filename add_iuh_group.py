import json
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

p = r'c:\Users\Admin\Documents\HUIT\config_iuh.json'
with open(p, 'r', encoding='utf-8') as f:
    cfg = json.load(f)

groups = cfg.get("zalo", {}).get("target_groups", [])

new_group = {
    "id": "4484187266322765997",
    "name": "TB điểm rèn luyện IUH",
    "type": "GROUP",
    "enabled": True
}

exists = any(str(g.get("id")) == str(new_group["id"]) for g in groups)
if not exists:
    groups.append(new_group)
    cfg["zalo"]["target_groups"] = groups
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print("Added 'TB điểm rèn luyện IUH' to config_iuh.json successfully!")
else:
    print("Group already exists in config_iuh.json")
