import asyncio
import aiohttp
import os
import json

# Replace with the real API key by fetching from Render dashboard or .env
# For this script we will require the real API Key

async def test_aio_stream(api_key):
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "text/event-stream"
    }
    payload = {
        "model": "meta/llama-3.3-70b-instruct",
        "messages": [{"role": "user", "content": "hello"}],
        "stream": True,
        "max_tokens": 1024
    }
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, headers=headers, json=payload) as response:
            print("Status:", response.status)
            count = 0
            async for line in response.content:
                print("RAW:", line)
                count += 1
                if count > 5: break

if __name__ == "__main__":
    key = os.getenv("RENDER_NVIDIA_API_KEY", "")
    if key:
        asyncio.run(test_aio_stream(key))
    else:
        print("Set RENDER_NVIDIA_API_KEY environment variable.")
