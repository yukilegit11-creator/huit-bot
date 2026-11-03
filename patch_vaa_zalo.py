with open(r'C:\Users\Admin\Documents\HUIT\vaa\ufm\zalo_sender.py', 'r', encoding='utf-8') as f:
    text = f.read()

old_z = '''    points_str_list = []
    if points > 0:
        points_str_list.append(f"+{points} ĐRL")
    if ctxh > 0:
        points_str_list.append(f"+{ctxh} CTXH")
    
    if points_str_list:
        lines.append(f"🎯 Điểm: {' | '.join(points_str_list)}")

    if event_time and event_time != "Chưa rõ thời gian":
        lines.append(f"⏰ Thời gian: {event_time}")'''

new_z = '''    now_vn = datetime.now(timezone(timedelta(hours=7))).strftime("%H:%M:%S %d/%m/%Y")
    posted_time = act.get("posted_time") or act.get("first_seen") or now_vn

    points_str_list = []
    if points > 0:
        points_str_list.append(f"+{points:g} ĐRL")
    if ctxh > 0:
        points_str_list.append(f"+{ctxh:g} CTXH")
    
    if points_str_list:
        lines.append(f"🎯 Điểm: {' • '.join(points_str_list)}")

    lines.append(f"⏰ Thời gian đăng bài: {posted_time}")

    if event_time and event_time != "Chưa rõ thời gian":
        lines.append(f"📅 Thời gian diễn ra: {event_time}")'''

assert old_z in text, "old_z not found in vaa/ufm/zalo_sender.py"
text = text.replace(old_z, new_z)
with open(r'C:\Users\Admin\Documents\HUIT\vaa\ufm\zalo_sender.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Updated vaa/ufm/zalo_sender.py successfully!')
