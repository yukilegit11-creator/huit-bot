import os

files_to_patch = [
    r'c:\Users\Admin\Documents\HUIT\bot.py',
    r'c:\Users\Admin\Documents\HUIT\vaabot.py',
    r'c:\Users\Admin\Documents\HUIT\iuh_bot.py',
    r'c:\Users\Admin\Documents\HUIT\ufm_bot.py',
    r'c:\Users\Admin\Documents\HUIT\vaa\ufm\bot.py'
]

for p in files_to_patch:
    if not os.path.exists(p):
        continue
    with open(p, 'r', encoding='utf-8') as f:
        content = f.read()

    # Bot 1 HUIT
    content = content.replace(
        'database.log_event("SCAN", f"🔄 [{database.get_vn_now_str()}] Chu kỳ #{cycle}: Bắt đầu quét {len(targets)} trang mục tiêu.")',
        'database.log_event("SCAN", f"🔄 Chu kỳ #{cycle}: Bắt đầu quét {len(targets)} trang mục tiêu.")'
    )
    content = content.replace(
        'database.log_event("SCAN", f"✅ [{database.get_vn_now_str()}] Chu kỳ #{cycle}: Hoàn tất quét {len(targets)} trang. Tạm nghỉ {check_interval}s trước vòng tiếp theo.")',
        'database.log_event("SCAN", f"✅ Chu kỳ #{cycle}: Hoàn tất quét {len(targets)} trang. Tạm nghỉ {check_interval}s trước vòng tiếp theo.")'
    )

    # Bot 2 VAA
    content = content.replace(
        'database.log_event("SCAN", f"🔄 [{database.get_vn_now_str()}] Chu kỳ #{cycle}: Bắt đầu quét {len(targets)} trang mục tiêu.", db_file=DB_TARGET)',
        'database.log_event("SCAN", f"🔄 Chu kỳ #{cycle}: Bắt đầu quét {len(targets)} trang mục tiêu.", db_file=DB_TARGET)'
    )
    content = content.replace(
        'database.log_event("SCAN", f"✅ [{database.get_vn_now_str()}] Chu kỳ #{cycle}: Hoàn tất quét {len(targets)} trang mục tiêu. Tạm nghỉ {check_interval}s trước vòng tiếp theo.", db_file=DB_TARGET)',
        'database.log_event("SCAN", f"✅ Chu kỳ #{cycle}: Hoàn tất quét {len(targets)} trang mục tiêu. Tạm nghỉ {check_interval}s trước vòng tiếp theo.", db_file=DB_TARGET)'
    )

    # Bot 3 IUH
    content = content.replace(
        'database.log_event("SCAN", f"🔄 [{now_str}] Chu kỳ #{cycle}: Quét xong cổng ĐRL IUH ({len(activities)} hoạt động).", db_file=DB_TARGET)',
        'database.log_event("SCAN", f"🔄 Chu kỳ #{cycle}: Quét xong cổng ĐRL IUH ({len(activities)} hoạt động).", db_file=DB_TARGET)'
    )

    # Bot 4 UFM
    content = content.replace(
        'database.log_event("SCAN", f"🔄 [{now_str}] Chu kỳ #{cycle}: Hoàn tất kiểm tra cổng ĐRL UFM ({len(activities)} hoạt động).", db_file=DB_TARGET)',
        'database.log_event("SCAN", f"🔄 Chu kỳ #{cycle}: Hoàn tất kiểm tra cổng ĐRL UFM ({len(activities)} hoạt động).", db_file=DB_TARGET)'
    )
    content = content.replace(
        'database.log_event("SCAN", f"🔄 [{now_str}] Chu kỳ #{cycle}: Hoàn tất kiểm tra cổng ĐRL UFM ({len(activities)} hoạt động).")',
        'database.log_event("SCAN", f"🔄 Chu kỳ #{cycle}: Hoàn tất kiểm tra cổng ĐRL UFM ({len(activities)} hoạt động).")'
    )

    with open(p, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Cleaned timestamp from {p}")
