import os

p = r'c:\Users\Admin\Documents\HUIT\vaa\ufm\database.py'
with open(p, 'r', encoding='utf-8') as f:
    text = f.read()

old_str = 'DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ufm_bot.db")'
new_str = '''# Thống nhất CSDL UFM về chung root repo ufm_bot.db
_root_db = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "ufm_bot.db")
DB_FILE = _root_db'''

if old_str in text:
    text = text.replace(old_str, new_str, 1)
    with open(p, 'w', encoding='utf-8') as f:
        f.write(text)
    print("Successfully replaced DB_FILE path in vaa/ufm/database.py")
else:
    print("old_str not found")
