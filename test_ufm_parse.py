import sys, json, requests, re
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with open(r'C:\Users\Admin\Documents\HUIT\config_ufm.json', 'r', encoding='utf-8') as f:
    cfg = json.load(f)

cookies = cfg['ufm_portal']['cookies']

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer': 'https://hoatdong.ufm.edu.vn/'
})
for k, v in cookies.items():
    s.cookies.set(k, v, domain='hoatdong.ufm.edu.vn')

r = s.get('https://hoatdong.ufm.edu.vn/DangKy', verify=False, timeout=15)
soup = BeautifulSoup(r.text, 'html.parser')

activities = []
for h5 in soup.find_all('h5'):
    full_title = h5.get_text(separator=' ', strip=True)
    if not full_title:
        continue
    
    id_m = re.search(r'\[ID\s*(\d+)\]', full_title, re.IGNORECASE)
    a_tag = h5.find('a')
    detail_path = a_tag.get('href', '') if a_tag else ''
    
    if id_m:
        raw_id = id_m.group(1).strip()
        clean_title = re.sub(r'\[ID\s*\d+\]\s*', '', full_title).strip()
    elif 'Details/' in detail_path:
        m2 = re.search(r'Details/([a-zA-Z0-9_-]+)', detail_path)
        raw_id = m2.group(1) if m2 else full_title[:20]
        clean_title = full_title
    else:
        continue

    activity_id = f'UFM_{raw_id}'
    detail_url = f'https://hoatdong.ufm.edu.vn{detail_path}' if detail_path.startswith('/') else (detail_path or 'https://hoatdong.ufm.edu.vn/DangKy')

    container = h5.find_parent('div', class_='p-5') or h5.find_parent('div')
    card = container.parent if container else h5.parent

    unit = 'Chưa rõ đơn vị'
    event_time = 'Chưa rõ thời gian'
    location = 'Chưa rõ địa điểm'
    group_criteria = ''
    points = 0.0
    ctxh = 0.0

    if container:
        for p in container.find_all('p'):
            txt = p.get_text(separator=' ', strip=True)
            txt_lower = txt.lower()
            if 'đơn vị:' in txt_lower:
                unit = txt.split(':', 1)[1].strip()
                if '|' in unit:
                    unit = unit.split('|')[0].strip()
            if 'thời gian:' in txt_lower:
                event_time = txt.split(':', 1)[1].strip()
                if '|' in event_time:
                    event_time = event_time.split('|')[0].strip()
            if 'địa điểm:' in txt_lower:
                location = txt.split(':', 1)[1].strip()
                if '|' in location:
                    location = location.split('|')[0].strip()
            if 'nhóm:' in txt_lower:
                group_criteria = txt.split(':', 1)[1].strip()
                pt_match = re.search(r'([\d\.]+)\s*(?:đrl|điểm)', txt, re.IGNORECASE)
                if pt_match:
                    try:
                        points = float(pt_match.group(1))
                    except Exception:
                        pass
                ctxh_match = re.search(r'(\d+)\s*ctxh', txt, re.IGNORECASE)
                if ctxh_match:
                    try:
                        ctxh = float(ctxh_match.group(1))
                    except Exception:
                        pass

    # Slot & Status extraction
    card_text = card.get_text(separator=' ', strip=True)
    slot_match = re.search(r'Số\s*lượng\s*:\s*(\d+\s*/\s*\d+)', card_text, re.IGNORECASE)
    if not slot_match:
        slot_match = re.search(r'(\d+\s*/\s*\d+)\s*(?:\(Đã đầy\)|\(Còn slot\))', card_text, re.IGNORECASE)
    slots = slot_match.group(1).replace(' ', '') if slot_match else 'Không giới hạn'

    is_full = False
    status = 'Đang mở đăng ký'
    if 'hủy' in card_text.lower() and ('frm-cancel' in str(card) or 'HuyDangKy' in str(card)):
        status = f'Đã đăng ký ({slots})'
        is_full = False
    elif any(k in card_text.lower() for k in ['đã đủ số lượng', 'đã đầy', 'hết slot', 'chưa mở', 'kết thúc']):
        status = f'Đã đủ số lượng ({slots})'
        is_full = True
    elif 'đăng ký' in card_text.lower():
        status = f'Đang mở đăng ký ({slots})'
        is_full = False

    activities.append({
        'activity_id': activity_id,
        'raw_id': raw_id,
        'title': clean_title,
        'unit': unit,
        'event_time': event_time,
        'location': location,
        'group_criteria': group_criteria,
        'points': points,
        'ctxh': ctxh,
        'status': status,
        'slots': slots,
        'is_full': is_full,
        'detail_url': detail_url,
        'register_url': 'https://hoatdong.ufm.edu.vn/DangKy',
        'source': 'Trang Mở Đăng Ký UFM (/DangKy)'
    })

print(f'Successfully parsed {len(activities)} activities from /DangKy!')
for a in activities:
    print(f"[{a['raw_id']}] {a['title']}")
    print(f"   Đơn vị: {a['unit']} | Thời gian: {a['event_time']} | ĐRL: +{a['points']} | Trạng thái: {a['status']} | Full: {a['is_full']}")
