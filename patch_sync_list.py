import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open("c:/Users/Admin/Documents/HUIT/sync_to_vps.py", "r", encoding="utf-8") as f:
    text = f.read()

target = '    ("vaa/ufm/fb_cookies.json", "/root/huit-bot/vaa/ufm/fb_cookies.json"),'
replacement = '''    ("vaa/ufm/fb_cookies.json", "/root/huit-bot/vaa/ufm/fb_cookies.json"),
    ("vaa/ufm/templates/index.html", "/root/huit-bot/vaa/ufm/templates/index.html"),'''

text = text.replace(target, replacement)
with open("c:/Users/Admin/Documents/HUIT/sync_to_vps.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Added templates/index.html to sync_to_vps.py!")
