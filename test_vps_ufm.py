import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import urllib.request
import json

def test_vps():
    print("Testing http://180.93.125.40:8000/ufm/ ...")
    req = urllib.request.urlopen("http://180.93.125.40:8000/ufm/", timeout=10)
    html = req.read().decode("utf-8")
    print(f"Status: {req.status}, Length: {len(html)}")
    print("Has 'UFM Portal Feed':", "UFM Portal Feed" in html)
    print("Has 'Plus Jakarta Sans':", "Plus Jakarta Sans" in html)
    print("Has 'bot-toggle-btn-bot4':", "bot-toggle-btn-bot4" in html)

    print("\nTesting http://180.93.125.40:8000/ufm/api/status ...")
    req_status = urllib.request.urlopen("http://180.93.125.40:8000/ufm/api/status", timeout=10)
    data = json.loads(req_status.read().decode("utf-8"))
    print("Status response:", json.dumps(data, indent=2, ensure_ascii=False))

    print("\nTesting http://180.93.125.40:8000/ufm/api/zalo/send-test-target ...")
    req_post = urllib.request.Request(
        "http://180.93.125.40:8000/ufm/api/zalo/send-test-target",
        data=json.dumps({"target_id": "7456361874031804652", "target_name": "demo"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    res_post = urllib.request.urlopen(req_post, timeout=15)
    post_data = json.loads(res_post.read().decode("utf-8"))
    print("Test Zalo send response:", post_data)

test_vps()
