import requests, urllib3
from bs4 import BeautifulSoup
urllib3.disable_warnings()

r = requests.get('https://doantn.iuh.edu.vn/login.html', verify=False)
soup = BeautifulSoup(r.text, 'html.parser')
for s in soup.find_all('script'):
    txt = s.get_text()
    if 'frmLogin' in txt or 'login' in txt.lower():
        print('Script content:')
        print(txt)
