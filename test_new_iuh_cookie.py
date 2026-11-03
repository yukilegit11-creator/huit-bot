import sys
from iuh_scraper import IUHPortalScraper

sys.stdout.reconfigure(encoding='utf-8')

new_cookie = "vfbsgb1d91o2ainlfge5p414ep"
scraper = IUHPortalScraper(cookie_raw=new_cookie)
is_valid, msg, acts = scraper.fetch_activities()
print("Cookie Valid:", is_valid)
print("Message:", msg)
print("Total Activities fetched:", len(acts))
for a in acts:
    print(f"[{a.get('id')}] {a.get('title')} | Điểm: {a.get('points')} | Hạn: {a.get('deadline')} | Trạng thái: {a.get('status')} | Số lượng: {a.get('slots')}")
