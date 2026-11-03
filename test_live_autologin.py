import sys
sys.path.insert(0, '/root/huit-bot')
from iuh_scraper import IUHPortalScraper

# Initialize scraper with NO session, but with student credentials
scraper = IUHPortalScraper(
    cookie_raw='',
    username='25640491',
    password='11022007',
    config_path='/root/huit-bot/config_iuh.json',
    auto_relogin=True
)

print('Testing fetch_activities with auto-login on VPS...')
ok, msg, acts = scraper.fetch_activities()
print('Result OK:', ok)
print('Message:', msg)
print('Activities fetched:', len(acts))
print('New PHPSESSID obtained:', scraper.phpsessid)
