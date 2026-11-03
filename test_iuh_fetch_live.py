import json
from iuh_scraper import IUHPortalScraper

with open('/root/huit-bot/config_iuh.json') as f:
    cfg = json.load(f)

p = cfg.get('portal', {})
phpsessid = p.get('phpsessid', '')
username = p.get('username', '')
password = p.get('password', '')

scraper = IUHPortalScraper(phpsessid, username=username, password=password, config_path='/root/huit-bot/config_iuh.json', auto_relogin=True)
ok, msg, acts = scraper.fetch_activities()
print(f"fetch_activities result: ok={ok}, msg={msg}, count={len(acts)}")
for a in acts:
    print(f"  [{a.get('activity_id')}] {a.get('title')} -- Status: {a.get('status')} -- Slots: {a.get('slots')} -- Points: {a.get('points')}")
