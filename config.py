import os

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")  # e.g. https://your-app.onrender.com

# NVIDIA AI
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

# Models
CHAT_MODEL = "mistralai/mistral-large-3-675b-instruct-2512"
VISION_MODEL = "meta/llama-4-scout-17b-16e-instruct"  # supports vision (must keep)
CODE_MODEL = "mistralai/mistral-large-3-675b-instruct-2512"
DOC_MODEL = "mistralai/mistral-large-3-675b-instruct-2512"

# Selectable models for /model command (vision excluded — handled automatically)
SELECTABLE_MODELS = {
    "1": ("mistralai/mistral-large-3-675b-instruct-2512",  "🥇 Mistral Large 3 675B — Largest & most powerful"),
    "2": ("qwen/qwen3-coder-480b-a35b-instruct",           "👨‍💻 Qwen3 Coder 480B — Best for code"),
    "3": ("qwen/qwen3.5-397b-a17b",                        "⚡ Qwen 3.5 397B — Fast & powerful"),
    "4": ("nvidia/llama-3.1-nemotron-ultra-253b-v1",       "🔬 Nemotron Ultra 253B — NVIDIA reasoning"),
    "5": ("meta/llama-3.1-405b-instruct",                  "🦙 Llama 3.1 405B — Meta's largest"),
}

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
