import asyncio
import aiohttp
import json

async def main():
    print("Testing post...")
    headers = {
        "Authorization": "Bearer ",
        "Accept": "text/event-stream",
    }
    payload = {
        "model": "meta/llama-3.3-70b-instruct",
        "messages": [{"role": "user", "content": "hello"}],
        "stream": True,
        "max_tokens": 1024,
        "temperature": 0.2,
        "top_p": 0.7,
        "top_k": 20,
        "presence_penalty": 0,
        "repetition_penalty": 1,
    }

    try:
        async with aiohttp.ClientSession() as s:
            print("Sending POST...")
            async with s.post('https://integrate.api.nvidia.com/v1/chat/completions', headers=headers, json=payload) as r:
                print("STATUS", r.status)
                r.raise_for_status()
                print("Reading lines...")
                async for line in r.content:
                    print(line)
    except Exception as e:
        print("CAUGHT:", e)
    print("Exit.")

asyncio.run(main())
