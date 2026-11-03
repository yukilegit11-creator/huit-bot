import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import urllib.request
import json

def check_logs():
    req = urllib.request.urlopen("http://180.93.125.40:8000/api/logs?limit=15", timeout=10)
    data = json.loads(req.read().decode("utf-8"))
    print("Latest 15 logs from Bot 1 (HUIT):")
    for l in data.get("logs", []):
        print(f"[{l.get('created_at')}] [{l.get('level')}] {l.get('message')}")

check_logs()
