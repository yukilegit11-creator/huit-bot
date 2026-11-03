import os
import sys
import json

sys.path.insert(0, '/root/huit-bot')
from messenger_sender import MessengerDispatcher

print("Initializing MessengerDispatcher...")
msger = MessengerDispatcher('/root/huit-bot/config.json')
ok = msger.connect()
print('Connect result:', ok)
if ok:
    groups = msger.fetch_all_groups()
    print('Fetched groups count:', len(groups))
    for g in groups:
        print('Group:', g)
else:
    print('Failed to connect to Facebook Messenger.')
