import requests
import io
from PIL import Image

url = "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1d/Taj_Mahal_%28Edited%29.jpg/800px-Taj_Mahal_%28Edited%29.jpg"

print("--- Without User-Agent ---")
try:
    resp = requests.get(url)
    print("Status code:", resp.status_code)
    img = Image.open(io.BytesIO(resp.content))
    print("Success! Image size:", img.size)
except Exception as e:
    print("Error:", type(e).__name__, e)

print("\n--- With User-Agent ---")
try:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    resp = requests.get(url, headers=headers)
    print("Status code:", resp.status_code)
    img = Image.open(io.BytesIO(resp.content))
    print("Success! Image size:", img.size)
except Exception as e:
    print("Error:", type(e).__name__, e)
