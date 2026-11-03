import asyncio
import sys
import json
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

EMAIL = "fat14112008@gmail.com"
PASSWORD = "YUKILEGIT0"

async def test_chrome_login():
    print("Launching real Chrome with Playwright...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            channel="chrome",
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            locale="vi-VN",
            viewport={"width": 1280, "height": 800}
        )
        page = await context.new_page()
        print("Navigating to https://www.facebook.com/login ...")
        await page.goto("https://www.facebook.com/login", timeout=30000)
        
        await page.fill('input[name="email"]', EMAIL)
        await page.fill('input[name="pass"]', PASSWORD)
        await page.keyboard.press("Enter")
        
        print("Submitted login. Waiting 8s...")
        await page.wait_for_timeout(8000)
        print("Page URL:", page.url)
        print("Page Title:", await page.title())

        cookies = await context.cookies()
        c_user = next((c for c in cookies if c["name"] == "c_user"), None)
        xs = next((c for c in cookies if c["name"] == "xs"), None)

        if c_user and xs:
            print(f"🎉 ĐĂNG NHẬP THÀNH CÔNG! UID: {c_user['value']}")
            with open("c:/Users/Admin/Documents/HUIT/fb_cookies.json", "w", encoding="utf-8") as f:
                json.dump(cookies, f, indent=2, ensure_ascii=False)
            print("Đã lưu cookie mới vào fb_cookies.json!")
        else:
            print("Chưa có c_user/xs.")
            await page.screenshot(path="c:/Users/Admin/Documents/HUIT/fb_chrome_res.png")
            print("Saved fb_chrome_res.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_chrome_login())
