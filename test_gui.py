import asyncio
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def test_gui():
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            await page.goto("https://www.google.com")
            print("GUI browser launched successfully!")
            await asyncio.sleep(2)
            await browser.close()
    except Exception as e:
        print("GUI error:", e)

asyncio.run(test_gui())
