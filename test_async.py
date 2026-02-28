import asyncio
import logging
import json
import nvidia_client as ai

logging.basicConfig(level=logging.DEBUG)

async def test_chat():
    history = [{'role': 'user', 'content': 'hello, say hi back'}]
    print("Testing chat API...")
    try:
        async for chunk in ai.chat(history):
            print(f"CHUNK: {chunk}")
        print("Done.")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_chat())
