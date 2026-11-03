
import urllib.request, json, ssl
with open('/root/huit-bot/fb_cookies.json') as f:
    cookies = json.load(f)

# Only send essential cookies
c_dict = {c['name']: c['value'] for c in cookies if c['name'] in ['c_user', 'xs', 'fr', 'datr', 'sb']}
c_str = '; '.join([f'{k}={v}' for k, v in c_dict.items()])

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(
    'https://mbasic.facebook.com/',
    headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Cookie': c_str,
    }
)
try:
    with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
        html = r.read().decode('utf-8', errors='ignore')
        print('Status:', r.status)
        print('URL:', r.geturl())
        if 'mbasic_logout_button' in html or 'logout.php' in html:
            print('Mbasic: LOGGED IN!')
        else:
            print('Mbasic: NOT LOGGED IN / REDIRECTED TO LOGIN')
except Exception as e:
    print('Error:', e)
