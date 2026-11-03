import json, re, urllib.request, ssl
with open('/root/huit-bot/fb_cookies.json', 'r') as f:
    cookies = json.load(f)

cookie_str = '; '.join([f"{c['name']}={c['value']}" for c in cookies])

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(
    'https://www.facebook.com/',
    headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Cookie': cookie_str,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
    }
)

with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
    html = resp.read().decode('utf-8', errors='ignore')
    print('Response status:', resp.status)
    print('HTML length:', len(html))
    print('Final URL:', resp.geturl())
    
    pos = html.find('DTSGInitialData')
    if pos != -1:
        print('DTSGInitialData chunk:', html[pos:pos+300])
    else:
        print('DTSGInitialData NOT found')
        
    pos_ag = html.find('async_get_token')
    if pos_ag != -1:
        print('async_get_token chunk:', html[pos_ag-50:pos_ag+200])
    else:
        print('async_get_token NOT found in HTML')
