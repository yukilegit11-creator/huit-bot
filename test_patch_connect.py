import sys
import re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import fbchat_muqit.utils.stateHelper as stateHelper
import fbchat_muqit.state as fb_state

def patched_extract_tokens_from_html(html: str):
    fb_dtsg = re.search(r'"DTSGInitialData".*?"token":"(.*?)"', html)
    if fb_dtsg:
        fb_dtsg = fb_dtsg.group(1)
    else:
        raise stateHelper.ValidationError("'fb_dtsg' token not found.")

    pattern = r'"DTSGInitData"(?:\s*,\s*\[\])?(?:\s*,\s*)\{[^}]*"async_get_token"\s*:\s*"([^"]*)"[^}]*\}'
    fb_dtsg_ag = re.search(pattern, html)
    if fb_dtsg_ag and fb_dtsg_ag.group(1):
        fb_dtsg_ag = fb_dtsg_ag.group(1)
    else:
        fb_dtsg_ag = fb_dtsg

    lsd_token = re.search(
        r'"LSD"\s*,\s*\[\s*\]\s*,\s*\{\s*"token"\s*:\s*"([A-Za-z0-9_-]+)"', html
    )
    if lsd_token:
        lsd_token = lsd_token.group(1)
    else:
        lsd_token = ""

    jazoest = "2" + str(sum(ord(c) for c in fb_dtsg))
    jazoest_async = "2" + str(sum(ord(c) for c in fb_dtsg_ag))

    clientRevision = re.search(r'client_revision":(\d+)', html)
    clientRevision = int(clientRevision.group(1)) if clientRevision else 1000

    clientID = re.search(
        r'\["MqttWebDeviceID".*?"clientID"\s*:\s*"([a-f0-9\-]+)"', html
    )
    clientID = clientID.group(1) if clientID else ""

    mqttAppID = re.search(r'\["MqttWebConfig".*?"appID"\s*:\s*(\d+)', html)
    mqttAppID = mqttAppID.group(1) if mqttAppID else "219994525426954"

    userAppID = re.search(r'\["CurrentUserInitialData".*?"APP_ID"\s*:\s*"(\d+)"', html)
    userAppID = userAppID.group(1) if userAppID else "2220391788200892"

    mqttEndpoint = re.search(
        r'"endpoint"\s*:\s*"([^"]*?region=([a-zA-Z0-9_-]+)[^"]*)"', html
    )
    if mqttEndpoint:
        endpoint = mqttEndpoint.group(1).encode().decode("unicode_escape")
        region = mqttEndpoint.group(2)
    else:
        ep_match = re.search(r'\["MqttWebConfig"[^\]]*\{[^}]*"endpoint"\s*:\s*"([^"]+)"', html) or re.search(r'"endpoint"\s*:\s*"(wss:[^"]+)"', html)
        if ep_match:
            endpoint = ep_match.group(1).encode().decode("unicode_escape")
        else:
            endpoint = "wss://edge-chat.facebook.com/chat"
        region = "PRN"

    user_name = re.search(r'"NAME"\s*:\s*"([^"]+)"', html)
    user_name = user_name.group(1) if user_name else ""

    return (
        fb_dtsg,
        fb_dtsg_ag,
        lsd_token,
        jazoest,
        jazoest_async,
        clientRevision,
        clientID,
        mqttAppID,
        userAppID,
        endpoint,
        region,
        user_name,
    )

stateHelper.extract_tokens_from_html = patched_extract_tokens_from_html
fb_state.extract_tokens_from_html = patched_extract_tokens_from_html

# Now test MessengerDispatcher!
from messenger_sender import MessengerDispatcher
d = MessengerDispatcher(config_file=r'c:\Users\Admin\Documents\HUIT\config.json')
ok = d.connect()
print("🎉 Messenger connect result with patched tokens:", ok)
if ok:
    print("Fetching groups...")
    groups = d.fetch_all_groups()
    print("Found groups count:", len(groups))
