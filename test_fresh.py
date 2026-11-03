import requests
import json
import time
import sys

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

cookies = {
    "__zi-legacy": "3000.SSZzejyD6zOgdh2mtnLQWYQN_RAG01ICFjIXe9fEM8Wud-gic4rTY72RxwtNIbA7SvxleZan.1",
    "_ga": "GA1.2.1298407733.1793676454",
    "_zlang": "vn",
    "_ga_3EM8ZPYYN3": "GS2.2.s1793681845$o2$g1$t1793686259$j60$l0$h0",
    "_gid": "GA1.2.120731817.1793676458",
    "zpw_sek": "z58k.466784528.a0.eE8cb5WYmURRLqIBwiQMaB3ay_lf_BJehQcZswIrxgIXdl7YZ_x0exttuyQy-wkojiWitPWRcyUhn_hh8goMa0",
    "ZConsentDenied": "timestamp=1793679453752&location=https://zalo.me/pc",
    "__zi": "3000.SSZzejyD6zOgdh2mtnLQWYQN_RAG01ICFjIXe9fEM8Wud-gic4rTY72RxwtNIbA7SvxleZan.1",
    "_ga_YS1V643LGV": "GS2.1.s1793684527$o4$g0$t1793685836$j60$l0$h0",
    "app.event.zalo.me": "3236038380622178657",
    "zpsid": "6BEE.466784528.11.MW5QLtPPAnDcoFa8Ubah4mCgMIT0RnmhGcmPAtZZPa2hL7npTpLG-XnPAnC"
}

imei = "285b1ace-34e5-4df3-98af-ca447e3d9e9d-5d0dd425008d7328cff9cce489fb55f7"

from zlapi import ZaloAPI
from zlapi.models import Message, ThreadType

try:
    print(f"Test đăng nhập Zalo với IMEI {imei[:15]}...")
    client = ZaloAPI(phone="", password="", imei=imei, cookies=cookies)
    uid = client.uid() if callable(client.uid) else client.uid
    print(f"🎉🎉🎉 ĐĂNG NHẬP THÀNH CÔNG! UID: {uid}")

    demo_id = "475259879796859360"
    txt = "🔔 [BOT UFM - TEST TỰ ĐỘNG THÀNH CÔNG]\n✅ Đã xác thực Cookie Zalo thành công!\n🚀 Sẵn sàng tự động gửi thông báo vào nhóm demo."
    res = client.send(Message(text=txt), thread_id=demo_id, thread_type=ThreadType.GROUP)
    print("✅ ĐÃ GỬI THÀNH CÔNG TIN NHẮN VÀO NHÓM DEMO! Result:", res)
except Exception as e:
    import traceback
    print("❌ Lỗi zlapi:", e)
    traceback.print_exc()
