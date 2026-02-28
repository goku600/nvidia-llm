import asyncio
import aiohttp

async def main():
    print("Testing...")
    async with aiohttp.ClientSession() as s:
        async with s.post('https://integrate.api.nvidia.com/v1/chat/completions', headers={'Authorization': 'Bearer ', 'Accept': 'text/event-stream'}) as r:
            print("STATUS", r.status)
            r.raise_for_status()
            content = await r.read()
            print("CONTENT", content)

asyncio.run(main())
