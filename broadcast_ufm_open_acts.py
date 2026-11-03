
import json, time, sqlite3
from ufm_scraper import UFMPortalScraper
from zalo_sender import ZaloDispatcher
import database
from ufm_bot import send_zalo_ufm, DB_TARGET

with open('/root/huit-bot/config_ufm.json') as f:
    cfg = json.load(f)

p = cfg.get('ufm_portal', {})
scraper = UFMPortalScraper(p.get('cookies', {}), p.get('username'), p.get('password'), config_path='/root/huit-bot/config_ufm.json')
scraper.ensure_authenticated()

is_ok, msg, activities = scraper.fetch_all_events()
print(f"Fetched {len(activities)} events from UFM portal.")

zalo = ZaloDispatcher('/root/huit-bot/config_ufm.json', db_file=DB_TARGET)
zalo.bot_name = "Yuki 4 (UFM ĐRL)"
zalo.connect()

# Target open activities that students need to register for
open_acts = [
    a for a in activities 
    if any(k in a.get('activity_id', '') for k in ['16586', '16585', '16589', '16597', '16454', '16507'])
]

print(f"Found {len(open_acts)} target open activities to broadcast:")
for act in open_acts:
    aid = act.get('activity_id')
    title = act.get('title')
    print(f"\nBroadcasting: {title} ({aid})...")
    
    # Send via send_zalo_ufm
    ok = send_zalo_ufm(zalo, act, is_reopened=False)
    print(f"  Result for {aid}: {ok}")
    
    # Update DB
    database.record_seen_activity(act, is_sent=True, db_file=DB_TARGET)
    database.add_crawled_activity(act, action_type="NEW", is_sent=True, db_file=DB_TARGET)
    time.sleep(2)

print("\nDONE broadcasting all open UFM activities!")
