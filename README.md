# 🤖 NVIDIA AI Telegram Bot

A feature-rich Telegram bot powered by **NVIDIA AI APIs**, deployable on **Render free tier** via GitHub.

## ✨ Features

| Mode | Command | Description |
|------|---------|-------------|
| 💬 Chat Assistant | `/mode` → Chat | General conversation with memory |
| 👨‍💻 Code Assistant | `/mode` → Code | Write, debug, review & explain code |
| 📄 Document Q&A | `/mode` → Doc | Upload a file and ask questions about it |
| 🖼️ Image Analysis | `/mode` → Image | Send a photo for AI-powered visual analysis |

- **Conversation memory** — remembers last 20 messages per mode per user
- **Webhook-based** — efficient and reliable on Render free tier
- **Multi-user** — each user has independent sessions and history

---

## 🚀 Deployment Guide

### 1. Prerequisites

- A [Telegram Bot Token](https://t.me/BotFather) — create a bot via `/newbot`
- An [NVIDIA AI API Key](https://build.nvidia.com/) — sign up for free credits
- A [GitHub](https://github.com) account
- A [Render](https://render.com) account (free tier works)

---

### 2. Set Up the Project

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
```

> **Never commit your real API keys!** Use environment variables (see below).

---

### 3. Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

---

### 4. Deploy on Render

1. Go to [render.com](https://render.com) and click **New → Web Service**
2. Connect your GitHub repo
3. Render will detect `render.yaml` automatically — confirm the settings
4. Set the following **Environment Variables** in the Render dashboard:

| Variable | Value |
|----------|-------|
| `TELEGRAM_BOT_TOKEN` | Your token from @BotFather |
| `NVIDIA_API_KEY` | Your NVIDIA API key |
| `WEBHOOK_URL` | Your Render URL, e.g. `https://nvidia-ai-telegram-bot.onrender.com` |

5. Click **Deploy** — Render will build and start the bot automatically!

---

### 5. Keep the Bot Alive (Optional but Recommended)

Render free tier **spins down** after 15 minutes of inactivity. To prevent this:

- Sign up for [UptimeRobot](https://uptimerobot.com) (free)
- Add a new monitor: **HTTP(s)** → URL: `https://YOUR-APP.onrender.com/health`
- Set interval to **5 minutes**

This pings the `/health` endpoint and keeps your service awake.

---

## 🛠️ Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export TELEGRAM_BOT_TOKEN="your_token_here"
export NVIDIA_API_KEY="your_nvidia_key_here"
export WEBHOOK_URL="https://YOUR-APP.onrender.com"

# Run the bot
python main.py
```

> For local testing, use [ngrok](https://ngrok.com) to expose your local server:
> ```bash
> ngrok http 8000
> # Use the ngrok URL as your WEBHOOK_URL
> ```

---

## 📁 Project Structure

```
├── main.py           # Entry point, webhook server setup
├── handlers.py       # Telegram message & command handlers
├── nvidia_client.py  # NVIDIA AI API client (chat, code, doc, image)
├── session.py        # Per-user session & conversation memory
├── config.py         # Configuration & environment variables
├── requirements.txt  # Python dependencies
├── render.yaml       # Render deployment config
├── Dockerfile        # Docker container definition
└── README.md         # This file
```

---

## 🤖 Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message + mode picker |
| `/mode` | Switch between assistant modes |
| `/clear` | Clear conversation history |
| `/help` | Show help & tips |

---

## 📦 Tech Stack

- **[python-telegram-bot](https://python-telegram-bot.org/)** v21 — Telegram Bot API
- **[aiohttp](https://docs.aiohttp.org/)** — Async webhook HTTP server
- **[NVIDIA AI API](https://build.nvidia.com/)** — LLM & vision models
- **[pypdf](https://pypdf.readthedocs.io/)** — PDF text extraction
- **[Render](https://render.com)** — Free cloud hosting

---

## ⚙️ Configuration

All settings are in `config.py` and controlled via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | *(required)* | Your Telegram bot token |
| `NVIDIA_API_KEY` | *(required)* | NVIDIA AI API key |
| `WEBHOOK_URL` | *(required)* | Public URL of your Render service |
| `PORT` | `8000` | Server port |

---

## 🔒 Security Notes

- API keys are loaded from **environment variables only** — never hardcoded in committed code
- Each user's session is isolated in memory
- The webhook endpoint includes the bot token as a path secret

---

## 📄 License

MIT License — feel free to use, modify, and deploy!
