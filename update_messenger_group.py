import os
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT_DIR = r"C:\Users\Admin\Documents\HUIT"

configs = [
    os.path.join(ROOT_DIR, "config.json"),
    os.path.join(ROOT_DIR, "config_bot2.json"),
    os.path.join(ROOT_DIR, "config_iuh.json"),
    os.path.join(ROOT_DIR, "config_ufm.json"),
    os.path.join(ROOT_DIR, "vaabot.json"),
    os.path.join(ROOT_DIR, "vaa", "config.json"),
    os.path.join(ROOT_DIR, "vaa", "vaabot.json"),
    os.path.join(ROOT_DIR, "vaa", "ufm", "config.json"),
]

demo_thread_id = "1773570903700841"
demo_group_name = "Nhóm demo (Facebook Messenger)"

for cp in configs:
    if not os.path.exists(cp):
        continue
    with open(cp, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    
    if "messenger" not in cfg:
        cfg["messenger"] = {"enabled": True, "cookies": [], "target_groups": []}
    
    cfg["messenger"]["enabled"] = True
    
    # Update or add demo group
    tgs = cfg["messenger"].get("target_groups", [])
    found = False
    for g in tgs:
        if str(g.get("id")) == demo_thread_id:
            g["name"] = demo_group_name
            g["enabled"] = True
            found = True
            break
    if not found:
        tgs.append({
            "id": demo_thread_id,
            "name": demo_group_name,
            "type": "GROUP",
            "enabled": True
        })
    cfg["messenger"]["target_groups"] = tgs
    
    with open(cp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f"Updated messenger target_groups in {os.path.basename(cp)}")

print("All configs updated with Messenger Demo group (ID: 1773570903700841)!")
