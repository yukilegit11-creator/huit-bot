import json

configs = [
    r'c:\Users\Admin\Documents\HUIT\config.json',
    r'c:\Users\Admin\Documents\HUIT\config_bot2.json',
    r'c:\Users\Admin\Documents\HUIT\config_iuh.json',
    r'c:\Users\Admin\Documents\HUIT\config_ufm.json',
    r'c:\Users\Admin\Documents\HUIT\vaa\ufm\config.json'
]

auth_config = {
    "enabled": True,
    "password": "YUKILEGIT0"
}

for p in configs:
    try:
        with open(p, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        cfg["dashboard_auth"] = auth_config
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print(f"Updated {p} with dashboard_auth")
    except Exception as e:
        print(f"Error {p}: {e}")
