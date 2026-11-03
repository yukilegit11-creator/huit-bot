import json

p = r'c:\Users\Admin\Documents\HUIT\config.json'
with open(p, 'r', encoding='utf-8') as f:
    cfg = json.load(f)

targets = cfg.get("targets", [])

new_target = {
    "name": "Đoàn - Hội Khoa Luật HUIT",
    "url": "https://www.facebook.com/doanhoikhoaluathuit",
    "enabled": True
}

# Check if already present
exists = any("doanhoikhoaluathuit" in t.get("url", "").lower() for t in targets)
if not exists:
    targets.append(new_target)
    cfg["targets"] = targets
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print("Added Đoàn - Hội Khoa Luật HUIT to config.json! Total targets:", len(targets))
else:
    print("Already exists in targets!")
