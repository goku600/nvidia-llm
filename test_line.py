import aiohttp
import asyncio
from aiohttp import web

async def handle(request):
    response = web.StreamResponse()
    response.content_type = 'text/plain'
    await response.prepare(request)
    await response.write(b"data: 123\ndata: 456\n")
    await response.write(b"data: ")
    await asyncio.sleep(0.1)
    await response.write(b"789\n")
    return response

async def start_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8080)
    await site.start()
    return runner

async def test_client():
    async with aiohttp.ClientSession() as session:
        async with session.get('http://localhost:8080/') as resp:
            print("--- async for item in resp.content ---")
            async for item in resp.content:
                print(repr(item))
            
            # test iter_any
            print("--- iter_any ---")
            # this would consume already, need another request
            
async def main():
    runner = await start_server()
    await test_client()
    await runner.cleanup()

asyncio.run(main())
