import os, sys, json
sys.path.insert(0, '/root/huit-bot')
from messenger_sender import MessengerDispatcher

msger = MessengerDispatcher('/root/huit-bot/config.json')
ok = msger.connect()
print('Messenger connect status:', ok)
if ok:
    demo_id = '1773570903700841'
    succ, msg = msger.send_test_message(target_thread_id=demo_id, custom_message='[Test Antigravity] Messenger Bot Yuki hoạt động ổn định trên nhóm demo!')
    print('Send test message result:', succ, msg)
