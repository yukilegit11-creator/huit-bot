
fp = '/usr/local/lib/python3.10/dist-packages/fbchat_muqit/utils/stateHelper.py'
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()

target = '''    fb_dtsg_ag = re.search(pattern, html)
    if fb_dtsg_ag:
        fb_dtsg_ag = fb_dtsg_ag.group(1)
    else:
        raise ValidationError("'async_get_token' not found.")'''

replacement = '''    fb_dtsg_ag = re.search(pattern, html)
    if fb_dtsg_ag:
        fb_dtsg_ag = fb_dtsg_ag.group(1)
    else:
        # Fallback to fb_dtsg for modern Facebook SSR
        fb_dtsg_ag = fb_dtsg'''

if target in content:
    content = content.replace(target, replacement)
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(content)
    print('SUCCESSFULLY PATCHED stateHelper.py!')
else:
    print('Target pattern not found or already patched.')
