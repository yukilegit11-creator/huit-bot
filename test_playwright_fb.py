import asyncio
import sys
import json
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

EMAIL = "fat14112008@gmail.com"
PASSWORD = "YUKILEGIT0"

async def test_fb_login():
    print("Launching Chromium...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="vi-VN"
        )
        page = await context.new_page()
        print("Navigating to https://www.facebook.com/login ...")
        await page.goto("https://www.facebook.com/login", timeout=30000)
        
        print("Filling email and pass...")
        await page.fill('input[name="email"]', EMAIL)
        await page.fill('input[name="pass"]', PASSWORD)
        print("Pressing Enter to submit...")
        await page.keyboard.press("Enter")
        
        print("Waiting 10 seconds for navigation and cookies...")
        await page.wait_for_timeout(10000)
        print("Final URL:", page.url)
        print("Final Title:", await page.title())

        cookies = await context.cookies()
        c_user = next((c for c in cookies if c["name"] == "c_user"), None)
        xs = next((c for c in cookies if c["name"] == "xs"), None)

        await page.screenshot(path="c:/Users/Admin/Documents/HUIT/fb_after_login.png")
        print("Saved screenshot fb_after_login.png")

        if c_user and xs:
            print(f"🎉 ĐĂNG NHẬP THÀNH CÔNG! UID (c_user): {c_user['value']}")
            with open("c:/Users/Admin/Documents/HUIT/fb_cookies.json", "w", encoding="utf-8") as f:
                json.dump(cookies, f, indent=2, ensure_ascii=False)
            print("Đã lưu cookie mới vào fb_cookies.json!")
            return cookies
        else:
            print("Chưa có c_user/xs. Cookie names:", [c["name"] for c in cookies])
            return None

asyncio.run(test_fb_login())
