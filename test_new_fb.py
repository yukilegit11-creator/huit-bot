
import os, sys, json
sys.path.insert(0, '/root/huit-bot')
from messenger_sender import MessengerDispatcher

# Update config.json on VPS with new cookies
with open('/root/huit-bot/config.json', 'r') as f:
    cfg = json.load(f)

with open('/root/huit-bot/fb_cookies.json', 'r') as f:
    new_cookies = json.load(f)

cfg['messenger']['cookies'] = new_cookies
cfg['messenger']['enabled'] = True
with open('/root/huit-bot/config.json', 'w') as f:
    json.dump(cfg, f, indent=2)

print('Updated config.json on VPS with new cookies!')

msger = MessengerDispatcher('/root/huit-bot/config.json')
ok = msger.connect()
print('Messenger connect status:', ok)
if ok:
    demo_id = '1773570903700841'
    print(f'Sending test message to demo group {demo_id}...')
    succ, msg = msger.send_test_message(target_thread_id=demo_id)
    print('Send test message result:', succ, msg)
else:
    print('Failed to connect to Messenger with new cookies.')
