import requests, ddddocr, urllib3
urllib3.disable_warnings()

ocr = ddddocr.DdddOcr(show_ad=False)
s = requests.Session()
s.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})

for i in range(3):
    r = s.get('https://doantn.iuh.edu.vn/components/com_contact/captcha.php', verify=False)
    res = ocr.classification(r.content)
    print(f'Sample #{i+1} captcha solved:', res)
