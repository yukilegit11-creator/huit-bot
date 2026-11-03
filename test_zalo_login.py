import requests
import time

headers = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'vi,en-US;q=0.9,en;q=0.8',
    'Connection': 'keep-alive',
    'Origin': 'https://chat.zalo.me',
    'Referer': 'https://chat.zalo.me/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
}

raw_cookie = '__zi=3000.SSZzejyD6zOgdh2mtnLQWYQN_RAG01ICFjIXe9fEM8Wud-gic4rTY72RxwtNIbs6SvZkh3Sn.1; __zi-legacy=3000.SSZzejyD6zOgdh2mtnLQWYQN_RAG01ICFjIXe9fEM8Wud-gic4rTY72RxwtNIbs6SvZkh3Sn.1; _ga=GA1.2.2025814332.1793676729; _gid=GA1.2.1802147234.1793676744; _zlang=vn; app.event.zalo.me=3236038380622178657; zpsid=B8Bo.466784528.8.Ue6_-RCXxckZi3nmlo7kQyPId5-55zbJXnJSKxsRepXkBBaBiY6vWjaXxci; zpw_sek=gcbp.466784528.a0.UcJfLKZ-qJhBYrHN-Xg6JA0uuoVv8AG3YrRJFw4gr6UJBkL_aIZmAPTtp0wA9xjkfXGy0OZ7Ynkx6uORCd26J0'
headers['Cookie'] = raw_cookie

imeis = [
    'e2cacca8-12d3-483c-bf79-8665ab8a4b37-5d0dd425008d7328cff9cce489fb55f7',
    '285b1ace-34e5-4df3-98af-ca447e3d9e9d-5d0dd425008d7328cff9cce489fb55f7'
]

for imei in imeis:
    url = f'https://wpa.chat.zalo.me/api/login/getLoginInfo?imei={imei}&type=30&client_version=645&computer_name=Web&ts={int(time.time()*1000)}'
    r = requests.get(url, headers=headers)
    print(imei[:10], r.status_code, r.text)
