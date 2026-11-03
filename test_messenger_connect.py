import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from messenger_sender import MessengerDispatcher

d = MessengerDispatcher(config_file=r'c:\Users\Admin\Documents\HUIT\config.json')
ok = d.connect()
print("Messenger connect result:", ok)
