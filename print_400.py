
import aiohttp, asyncio
from fbchat_muqit.utils.stateHelper import load_json_cookies_async

async def main():
    jar = await load_json_cookies_async('/root/huit-bot/fb_cookies.json')
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    async with aiohttp.ClientSession(cookie_jar=jar) as session:
        async with session.get('https://www.facebook.com/', headers=headers) as resp:
            text = await resp.text()
            print('Status:', resp.status)
            print('Headers:', dict(resp.headers))
            print('Body sample:')
            print(text[:1000])

asyncio.run(main())
