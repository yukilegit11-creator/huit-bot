
import aiohttp, asyncio, re
from fbchat_muqit.utils.stateHelper import load_json_cookies_async

async def main():
    jar = await load_json_cookies_async('/root/huit-bot/fb_cookies.json')
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    async with aiohttp.ClientSession(cookie_jar=jar) as session:
        async with session.get('https://www.facebook.com/', headers=headers) as resp:
            html = await resp.text()
            print('Status:', resp.status)
            print('URL:', resp.url)
            print('HTML len:', len(html))
            
            # Find all endpoint or wss or mqtt occurrences
            endpoints = re.findall(r'"endpoint"\s*:\s*"([^"]+)"', html)
            print('Endpoints found:', len(endpoints), endpoints[:5])
            
            wss = re.findall(r'wss://[^"\s]+', html)
            print('WSS found:', len(wss), wss[:5])
            
            regions = re.findall(r'region=[a-zA-Z0-9_-]+', html)
            print('Regions found:', len(regions), regions[:5])

            mqtt_conf = re.findall(r'\["MqttWebConfig".*?\]', html)
            print('MqttWebConfig found:', len(mqtt_conf), mqtt_conf[:2])

asyncio.run(main())
