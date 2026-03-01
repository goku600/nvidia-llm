import asyncio
import sys
sys.path.append(r'c:\Users\goku3\OneDrive\Desktop\nvidia-ai')
import config
import os
import nvidia_client as ai

# Bypass missing env locally
if not config.NVIDIA_API_KEY:
    config.NVIDIA_API_KEY = os.getenv("TEST_KEY", "")

async def run():
    print("Sending...")
    async for curr in ai.chat([{'role': 'user', 'content': 'hello'}]):
        print('CHUNK>>', curr)
    print("Done")

if __name__ == '__main__':
    asyncio.run(run())
