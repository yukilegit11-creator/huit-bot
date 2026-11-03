import json, sys
sys.stdout.reconfigure(encoding='utf-8')

config_paths = [
    r'c:\Users\Admin\Documents\HUIT\config.json',
    r'c:\Users\Admin\Documents\HUIT\config_bot2.json',
    r'c:\Users\Admin\Documents\HUIT\vaabot.json',
    r'c:\Users\Admin\Documents\HUIT\vaa\config.json',
    r'c:\Users\Admin\Documents\HUIT\vaa\vaabot.json'
]

keywords_to_add = ["chuyên đề", "chuyen de", "Chuyên đề"]

for path in config_paths:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    kws = data.get('filter_keywords', [])
    for kw in keywords_to_add:
        if kw not in kws:
            kws.append(kw)
    data['filter_keywords'] = kws
    
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Updated {path}: {data['filter_keywords']}")
