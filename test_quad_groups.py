import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
with urllib.request.urlopen('http://180.93.125.40:8000/api/zalo/quad-target-groups', timeout=10) as r:
    data = json.loads(r.read().decode('utf-8'))
print('Status:', data.get('status'))
for b in data.get('bots', []):
    print(f"{b['bot_id']} - {b['bot_name']}: {len(b.get('groups', []))} groups")
    for g in b.get('groups', []):
        print(f"   * {g.get('name')} (ID: {g.get('id')}, Type: {g.get('type')}, Enabled: {g.get('enabled')})")
