import os

# --- PATCH BOT.PY ---
bot_path = "c:/Users/Admin/Documents/HUIT/bot.py"
with open(bot_path, "r", encoding="utf-8") as f:
    bot_code = f.read()

old_bot_block = '''            print(f"👉 ({idx+1}/{len(targets)}) Đang quét: {page_name}")
            try:
                html = scraper.fetch_url(page_url)
                posts = scraper.parse_posts(html, max_age_hours=max_age_hours, page_url=page_url)
                print(f"   📊 Bóc tách được {len(posts)} bài viết mới (<= {max_age_hours}h).")

                for p in posts:'''

new_bot_block = '''            curr_idx = idx + 1
            total_targets = len(targets)
            print(f"👉 ({curr_idx}/{total_targets}) Đang quét: {page_name}")
            database.log_event("SCAN", f"🔍 [{curr_idx}/{total_targets}] Đang quét: {page_name}...")
            new_found = 0
            try:
                html = scraper.fetch_url(page_url)
                posts = scraper.parse_posts(html, max_age_hours=max_age_hours, page_url=page_url)
                print(f"   📊 Bóc tách được {len(posts)} bài viết mới (<= {max_age_hours}h).")

                for p in posts:'''

old_seen_inc = '''                    if not database.is_post_seen(ident, content=p["content"]):
                        total_new_posts += 1'''

new_seen_inc = '''                    if not database.is_post_seen(ident, content=p["content"]):
                        new_found += 1
                        total_new_posts += 1'''

old_sleep_block = '''            # Nghỉ giữa các trang để chống chặn rate limit từ Facebook
            sleep_time = random.uniform(delay_between_pages * 0.8, delay_between_pages * 1.2)
            time.sleep(sleep_time)

        database.set_bot_status("bot_state", "sleeping")
        print(f"💤 Đã hoàn thành vòng #{cycle}. Tạm nghỉ {check_interval} giây trước vòng tiếp theo...")
        database.log_event("SCAN", f"✅ Chu kỳ #{cycle}: Hoàn tất quét {len(targets)} trang. Tạm nghỉ {check_interval}s trước vòng tiếp theo.")'''

new_sleep_block = '''            # Nghỉ giữa các trang để chống chặn rate limit từ Facebook
            sleep_time = random.uniform(delay_between_pages * 0.8, delay_between_pages * 1.2)
            next_str = f"chuyển qua trang [{curr_idx+1}/{total_targets}]" if curr_idx < total_targets else "hoàn tất vòng quét"
            post_stat = f"phát hiện {new_found} bài mới" if new_found > 0 else "0 bài mới"
            database.log_event("SCAN", f"✅ [{curr_idx}/{total_targets}] Hoàn thành: {page_name} ({post_stat}). Nghỉ {int(sleep_time)}s -> {next_str}.")
            time.sleep(sleep_time)

        database.set_bot_status("bot_state", "sleeping")
        print(f"💤 Đã hoàn thành vòng #{cycle}. Tạm nghỉ {check_interval} giây trước vòng tiếp theo...")
        database.log_event("SCAN", f"🎉 Chu kỳ #{cycle}: Hoàn tất quét toàn bộ {len(targets)} trang. Tạm nghỉ {check_interval}s trước chu kỳ #{cycle+1}.")'''

if old_bot_block in bot_code:
    bot_code = bot_code.replace(old_bot_block, new_bot_block, 1)
    bot_code = bot_code.replace(old_seen_inc, new_seen_inc, 1)
    bot_code = bot_code.replace(old_sleep_block, new_sleep_block, 1)
    with open(bot_path, "w", encoding="utf-8") as f:
        f.write(bot_code)
    print("✅ Patched bot.py successfully!")
else:
    print("⚠️ Could not find exact block in bot.py")
