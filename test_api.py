import json
import requests
from config import NVIDIA_API_KEY, NVIDIA_API_URL

headers = {
    "Authorization": f"Bearer {NVIDIA_API_KEY}",
    "Accept": "application/json",
}

payload = {
    "model": "meta/llama-3.1-405b-instruct",
    "messages": [{"role": "user", "content": "hi"}],
    "max_tokens": 1024,
    "temperature": 0.2,
    "top_p": 0.7,
}

response = requests.post(NVIDIA_API_URL, headers=headers, json=payload)
print(response.status_code)
print(response.text)
