import asyncio
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def inspect_2fa():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await page.goto('https://www.facebook.com/login')
        await page.fill('input[name="email"]', 'fat14112008@gmail.com')
        await page.fill('input[name="pass"]', 'YUKILEGIT0')
        await page.keyboard.press('Enter')
        await page.wait_for_timeout(8000)
        
        text = await page.inner_text('body')
        print('=== 2FA PAGE TEXT ===')
        print(text[:1500])
        print('=== INPUTS ===')
        for inp in await page.query_selector_all('input'):
            n = await inp.get_attribute('name')
            ph = await inp.get_attribute('placeholder')
            tp = await inp.get_attribute('type')
            print(f"input: name={n}, placeholder={ph}, type={tp}")
        
        await page.screenshot(path="fb_2fa_screen.png")
        print("Saved fb_2fa_screen.png")
        await browser.close()

asyncio.run(inspect_2fa())
