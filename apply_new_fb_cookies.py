import json
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 1. COOKIES QUÉT HUIT (c_user: 61592903259792)
cookies_huit_list = [
    {
        "domain": ".facebook.com",
        "expirationDate": 1825779664.96011,
        "hostOnly": False,
        "httpOnly": True,
        "name": "ps_l",
        "path": "/",
        "sameSite": "lax",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "1"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1825779664.549106,
        "hostOnly": False,
        "httpOnly": True,
        "name": "datr",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "ztfDaj_5NKGnBN3r1C3aKdB-"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1801484783.594725,
        "hostOnly": False,
        "httpOnly": True,
        "name": "fr",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "19qyuaBvhTKYmFUxD.AWcgza68PFuukqYw0XXbgXYa86SkJDUDku7n4kP1IXAXuKIsQmo.Bq6dLt..AAA.0.0.Bq6dLt.AWcu4n02_Z4gPRPdyUO2MVQUNAM"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1825244783.59481,
        "hostOnly": False,
        "httpOnly": True,
        "name": "xs",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "13%3A5QhZm5V7iIIwyQ%3A2%3A1793565487%3A-1%3A-1%3A%3AAc2hX_buRyqH5pHLTJC_-JGDtyYweC9vwCIEJ-amwg"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1825244783.594582,
        "hostOnly": False,
        "httpOnly": False,
        "name": "c_user",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "61592903259792"
    },
    {
        "domain": ".facebook.com",
        "hostOnly": False,
        "httpOnly": False,
        "name": "presence",
        "path": "/",
        "sameSite": None,
        "secure": True,
        "session": True,
        "storeId": None,
        "value": "C%7B%22t3%22%3A%5B%5D%2C%22utc3%22%3A1793708783275%2C%22v%22%3A1%7D"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1794313582,
        "hostOnly": False,
        "httpOnly": False,
        "name": "dpr",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "1.3499999046325684"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1825779664.9602,
        "hostOnly": False,
        "httpOnly": True,
        "name": "ps_n",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "1"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1828125489.53099,
        "hostOnly": False,
        "httpOnly": True,
        "name": "sb",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "ztfDagnfYuiIXElW1JBf_Lsy"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1794313582,
        "hostOnly": False,
        "httpOnly": False,
        "name": "wd",
        "path": "/",
        "sameSite": "lax",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "1424x644"
    }
]
cookies_huit_dict = {c['name']: c['value'] for c in cookies_huit_list}

# 2. COOKIES QUÉT VAA (c_user: 100087432870248)
cookies_vaa_list = [
    {
        "domain": ".facebook.com",
        "expirationDate": 1825771628.167271,
        "hostOnly": False,
        "httpOnly": True,
        "name": "ps_l",
        "path": "/",
        "sameSite": "lax",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "1"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1825771586.549716,
        "hostOnly": False,
        "httpOnly": True,
        "name": "datr",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "QbjDap5S3XtDDPF8wUPLvuRU"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1801484839.245992,
        "hostOnly": False,
        "httpOnly": True,
        "name": "fr",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "1ta0PV5JoJsf44xQK.AWderoxfXNEFNdxNUlBb_GtLQH09ggN87ZKdwSVkNaAF1RANthI.Bq6dMY..AAA.0.0.Bq6dMk.AWdMelIuWNSitUe6sXZsAiM0nR4"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1825244827.503668,
        "hostOnly": False,
        "httpOnly": True,
        "name": "xs",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "20%3ADnGCXmH-2sB1vQ%3A2%3A1792852867%3A-1%3A-1%3A%3AAc1nZYFh651VvgtztzzypXdd9SquwcSHghqJk_0BRV8"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1825244827.503443,
        "hostOnly": False,
        "httpOnly": False,
        "name": "c_user",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "100087432870248"
    },
    {
        "domain": ".facebook.com",
        "hostOnly": False,
        "httpOnly": False,
        "name": "presence",
        "path": "/",
        "sameSite": None,
        "secure": True,
        "session": True,
        "storeId": None,
        "value": "C%7B%22t3%22%3A%5B%5D%2C%22utc3%22%3A1793708842074%2C%22v%22%3A1%7D"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1794313641,
        "hostOnly": False,
        "httpOnly": False,
        "name": "dpr",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "1.5"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1825771628.167374,
        "hostOnly": False,
        "httpOnly": True,
        "name": "ps_n",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "1"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1827412870.204081,
        "hostOnly": False,
        "httpOnly": True,
        "name": "sb",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "QbjDantBe3VGruYaEe2PSt3i"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1794313641,
        "hostOnly": False,
        "httpOnly": False,
        "name": "wd",
        "path": "/",
        "sameSite": "lax",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "1280x593"
    }
]
cookies_vaa_dict = {c['name']: c['value'] for c in cookies_vaa_list}

# 3. COOKIES GỬI MESSENGER (c_user: 61595329828799)
cookies_messenger_list = [
    {
        "domain": ".facebook.com",
        "expirationDate": 1828253638.676091,
        "hostOnly": False,
        "httpOnly": True,
        "name": "ps_l",
        "path": "/",
        "sameSite": "lax",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "1"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1828253437.025433,
        "hostOnly": False,
        "httpOnly": True,
        "name": "datr",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "-pbpavf2opPl_hPBKlMxbUIH"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1801484875.10707,
        "hostOnly": False,
        "httpOnly": True,
        "name": "fr",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "1APj3j657FwOoV8e5.AWeEWApea_wBQ2fknEnrDy7G9FzSnfmbta_x7_tjtVBAipEuJI0.Bq6dNI..AAA.0.0.Bq6dNI.AWdT7XY8no0S8IXko7OLjPfr2Tg"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1825244875.107142,
        "hostOnly": False,
        "httpOnly": True,
        "name": "xs",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "14%3AHcgpFYhcu3gPiw%3A2%3A1793705121%3A-1%3A-1%3A%3AAc0s2zC6XC4Y5OGGM3a1_elKwvJLPwVhemfjQMbVVw"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1825244875.106991,
        "hostOnly": False,
        "httpOnly": False,
        "name": "c_user",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "61595329828799"
    },
    {
        "domain": ".facebook.com",
        "hostOnly": False,
        "httpOnly": False,
        "name": "presence",
        "path": "/",
        "sameSite": None,
        "secure": True,
        "session": True,
        "storeId": None,
        "value": "C%7B%22lm3%22%3A%22g.1620250146795363%22%2C%22t3%22%3A%5B%5D%2C%22utc3%22%3A1793708880523%2C%22v%22%3A1%7D"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1794302633,
        "hostOnly": False,
        "httpOnly": False,
        "name": "dpr",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "0.75"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1828253638.676286,
        "hostOnly": False,
        "httpOnly": True,
        "name": "ps_n",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "1"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1828265125.311024,
        "hostOnly": False,
        "httpOnly": True,
        "name": "sb",
        "path": "/",
        "sameSite": "no_restriction",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "-5bpaiCSb5HDa411EdNDilYJ"
    },
    {
        "domain": ".facebook.com",
        "expirationDate": 1794313676,
        "hostOnly": False,
        "httpOnly": False,
        "name": "wd",
        "path": "/",
        "sameSite": "lax",
        "secure": True,
        "session": False,
        "storeId": None,
        "value": "1853x893"
    }
]

# A. CẬP NHẬT CONFIG BOT 1 (HUIT)
p_cfg1 = r'c:\Users\Admin\Documents\HUIT\config.json'
with open(p_cfg1, 'r', encoding='utf-8') as f:
    cfg1 = json.load(f)
cfg1["fb_cookies"] = cookies_huit_dict
if "messenger" not in cfg1: cfg1["messenger"] = {}
cfg1["messenger"]["cookies"] = cookies_messenger_list
with open(p_cfg1, 'w', encoding='utf-8') as f:
    json.dump(cfg1, f, ensure_ascii=False, indent=2)
print("✅ Đã cập nhật Cookie HUIT (61592903259792) và Messenger vào config.json")

# B. CẬP NHẬT CONFIG BOT 2 (VAA)
vaa_files = [
    r'c:\Users\Admin\Documents\HUIT\config_bot2.json',
    r'c:\Users\Admin\Documents\HUIT\vaabot.json',
    r'c:\Users\Admin\Documents\HUIT\vaa\config.json',
    r'c:\Users\Admin\Documents\HUIT\vaa\vaabot.json'
]
for p in vaa_files:
    try:
        with open(p, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        cfg["fb_cookies"] = cookies_vaa_dict
        if "messenger" not in cfg: cfg["messenger"] = {}
        cfg["messenger"]["cookies"] = cookies_messenger_list
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print(f"✅ Đã cập nhật Cookie VAA (100087432870248) vào {p}")
    except Exception as e:
        print(f"⚠️ Lỗi {p}: {e}")

# C. CẬP NHẬT COOKIE MESSENGER
msg_files = [
    r'c:\Users\Admin\Documents\HUIT\config_iuh.json',
    r'c:\Users\Admin\Documents\HUIT\config_ufm.json',
    r'c:\Users\Admin\Documents\HUIT\vaa\ufm\config.json'
]
for p in msg_files:
    try:
        with open(p, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        if "messenger" not in cfg: cfg["messenger"] = {}
        cfg["messenger"]["cookies"] = cookies_messenger_list
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print(f"✅ Đã cập nhật Messenger cookies vào {p}")
    except Exception as e:
        print(f"⚠️ Lỗi {p}: {e}")

# D. LƯU VÀO CÁC FILE fb_cookies.json
for p in [r'c:\Users\Admin\Documents\HUIT\fb_cookies.json', r'c:\Users\Admin\Documents\HUIT\vaa\ufm\fb_cookies.json']:
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(cookies_messenger_list, f, ensure_ascii=False, indent=2)
    print(f"✅ Đã lưu file {p}")
