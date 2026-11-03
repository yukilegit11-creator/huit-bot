import asyncio
import sys
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await page.goto("https://www.facebook.com/login", timeout=30000)
        
        # Check title and inputs
        print("Page title:", await page.title())
        inputs = await page.query_selector_all("input")
        for inp in inputs:
            n = await inp.get_attribute("name")
            i = await inp.get_attribute("id")
            t = await inp.get_attribute("type")
            print(f"Input: name={n}, id={i}, type={t}")
        
        buttons = await page.query_selector_all("button")
        for b in buttons:
            n = await b.get_attribute("name")
            i = await b.get_attribute("id")
            t = await b.get_attribute("type")
            txt = await b.inner_text()
            print(f"Button: name={n}, id={i}, type={t}, text={repr(txt)}")

        await page.screenshot(path="c:/Users/Admin/Documents/HUIT/fb_page.png")
        print("Saved fb_page.png")
        await browser.close()

asyncio.run(main())
