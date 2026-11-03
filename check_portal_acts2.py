
import json
from ufm_scraper import UFMPortalScraper

with open('/root/huit-bot/config_ufm.json') as f:
    cfg = json.load(f)

p = cfg.get('ufm_portal', {})
scraper = UFMPortalScraper(p.get('cookies', {}), p.get('username'), p.get('password'), config_path='/root/huit-bot/config_ufm.json')
scraper.ensure_authenticated()

is_ok, msg, activities = scraper.fetch_all_events()
print(f"Status: {is_ok} | msg: {msg} | Total: {len(activities)}")
for act in activities:
    print(f"  [{act.get('activity_id')}] {act.get('title')} | status: {act.get('status')} | slots: {act.get('slots')} | ĐRL: {act.get('points')} | is_full: {act.get('is_full')}")
