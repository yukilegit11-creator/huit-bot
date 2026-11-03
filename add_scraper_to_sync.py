p = r'c:\Users\Admin\Documents\HUIT\sync_to_vps.py'
with open(p, 'r', encoding='utf-8') as f:
    text = f.read()

target = '    ("messenger_sender.py", "/root/huit-bot/messenger_sender.py"),\n'
repl = '    ("messenger_sender.py", "/root/huit-bot/messenger_sender.py"),\n    ("scraper.py", "/root/huit-bot/scraper.py"),\n'

if target in text:
    text = text.replace(target, repl, 1)
    with open(p, 'w', encoding='utf-8') as f:
        f.write(text)
    print("Added scraper.py to sync_to_vps.py successfully!")
else:
    print("Target not found")
