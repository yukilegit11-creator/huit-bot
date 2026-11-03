import json
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

for path in [
    r'c:\Users\Admin\Documents\HUIT\config.json',
    r'c:\Users\Admin\Documents\HUIT\config_bot2.json',
    r'c:\Users\Admin\Documents\HUIT\vaa\config.json',
    r'c:\Users\Admin\Documents\HUIT\vaabot.json'
]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            c = cfg.get('fb_cookies', {})
            c_user = c.get('c_user', 'N/A')
            xs = c.get('xs', 'N/A')
            print(f"{path}: c_user={c_user}, xs={xs[:20]}...")
    except Exception as e:
        print(f"Err {path}: {e}")
