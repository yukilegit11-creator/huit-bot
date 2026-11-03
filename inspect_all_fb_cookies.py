import json
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

for path in [
    r'c:\Users\Admin\Documents\HUIT\config.json',
    r'c:\Users\Admin\Documents\HUIT\config_bot2.json',
    r'c:\Users\Admin\Documents\HUIT\vaabot.json',
    r'c:\Users\Admin\Documents\HUIT\fb_cookies.json'
]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if 'fb_cookies' in data:
                c = data['fb_cookies']
                print(f"{path}: fb_cookies keys={list(c.keys()) if isinstance(c, dict) else len(c)}")
            elif isinstance(data, list):
                names = [x.get('name') for x in data if isinstance(x, dict)]
                print(f"{path}: cookie list len={len(data)}, names={names[:5]}")
            else:
                print(f"{path}: keys={list(data.keys())[:5]}")
    except Exception as e:
        print(f"Error {path}: {e}")
