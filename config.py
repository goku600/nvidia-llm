import os

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")  # e.g. https://your-app.onrender.com

# NVIDIA AI
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

# Models
CHAT_MODEL = "qwen/qwen3.5-397b-a17b"
VISION_MODEL = "meta/llama-4-scout-17b-16e-instruct"  # supports vision
CODE_MODEL = "qwen/qwen3.5-397b-a17b"
DOC_MODEL = "qwen/qwen3.5-397b-a17b"

# Generation defaults
MAX_TOKENS = 16384
TEMPERATURE = 0.6
TOP_P = 0.95
TOP_K = 20

# App
PORT = int(os.getenv("PORT", 8000))
HOST = "0.0.0.0"

# Per-user history limit (messages kept in memory)
MAX_HISTORY_MESSAGES = 20
