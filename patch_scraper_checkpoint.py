with open('c:/Users/Admin/Documents/HUIT/scraper.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_str = 'if "checkpoint" in text_low or "/checkpoint/" in resp.url or \'id="login_top"\' in text_low or "/login/" in resp.url:'
new_str = 'is_chk = "/checkpoint/" in resp.url or "/login/" in resp.url or \'"is_checkpointed":true\' in text_low or \'id="login_top"\' in text_low\n                if is_chk:'

if old_str in content:
    content = content.replace(old_str, new_str)
    with open('c:/Users/Admin/Documents/HUIT/scraper.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS: Patched scraper.py!")
else:
    print("NOT FOUND")
