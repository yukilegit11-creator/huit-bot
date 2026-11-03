import json
from ufm_scraper import UFMPortalScraper

with open('/root/huit-bot/config_ufm.json') as f:
    cfg = json.load(f)

p = cfg.get('ufm_portal', {})
scraper = UFMPortalScraper(p.get('cookies', {}), p.get('username'), p.get('password'), config_path='/root/huit-bot/config_ufm.json')
ok, msg, acts = scraper.fetch_dangky_activities()
print(f"fetch_dangky_activities result: ok={ok}, count={len(acts)}")
for a in acts:
    print(f"  [{a.get('activity_id')}] {a.get('title')} -- Status: {a.get('status')} -- Full: {a.get('is_full')} -- Points: {a.get('points')}")
