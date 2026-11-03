import os, json

p1 = "c:/Users/Admin/Documents/HUIT/config_ufm.json"
p2 = "c:/Users/Admin/Documents/HUIT/vaa/ufm/config.json"

print("p1 exists:", os.path.exists(p1))
print("p2 exists:", os.path.exists(p2))

if os.path.exists(p1) and os.path.exists(p2):
    with open(p1, "r", encoding="utf-8") as f: c1 = json.load(f)
    with open(p2, "r", encoding="utf-8") as f: c2 = json.load(f)
    print("p1 zalo target_groups count:", len(c1.get("zalo", {}).get("target_groups", [])))
    print("p2 zalo target_groups count:", len(c2.get("zalo", {}).get("target_groups", [])))
    print("p1 has cookies:", bool(c1.get("zalo", {}).get("cookies")))
    print("p2 has cookies:", bool(c2.get("zalo", {}).get("cookies")))
