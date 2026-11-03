import requests

cookie_str = (
    "__zi-legacy=3000.SSZzejyD6zOgdh2mtnLQWYQN_RAG01ICFjIXe9fEM8Wud-gic4rTY72RxwtNIbA7SvxleZan.1; "
    "_ga=GA1.2.1298407733.1793676454; "
    "_zlang=vn; "
    "_ga_3EM8ZPYYN3=GS2.2.s1793681845$o2$g1$t1793686259$j60$l0$h0; "
    "_gid=GA1.2.120731817.1793676458; "
    "zpw_sek=z58k.466784528.a0.eE8cb5WYmURRLqIBwiQMaB3ay_lf_BJehQcZswIrxgIXdl7YZ_x0exttuyQy-wkojiWitPWRcyUhn_hh8goMa0; "
    "__zi=3000.SSZzejyD6zOgdh2mtnLQWYQN_RAG01ICFjIXe9fEM8Wud-gic4rTY72RxwtNIbA7SvxleZan.1; "
    "app.event.zalo.me=3236038380622178657; "
    "zpsid=6BEE.466784528.11.MW5QLtPPAnDcoFa8Ubah4mCgMIT0RnmhGcmPAtZZPa2hL7npTpLG-XnPAnC"
)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "sec-ch-ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "origin": "https://chat.zalo.me",
    "referer": "https://chat.zalo.me/",
    "Cookie": cookie_str
}

imeis = [
    "285b1ace-34e5-4df3-98af-ca447e3d9e9d-5d0dd425008d7328cff9cce489fb55f7",
    "4082051c-a29c-4750-98bd-af0dfc1ea667-5d0dd425008d7328cff9cce489fb55f7"
]

for im in imeis:
    url = f"https://wpa.chat.zalo.me/api/login/getLoginInfo?imei={im}&type=30&client_version=645"
    r = requests.get(url, headers=headers)
    print(f"Test Win UA [{im[:15]}...]: {r.status_code} -> {r.text}")
