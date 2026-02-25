"""
In-memory session store for per-user conversation history and mode tracking.
On Render free tier, memory is reset when the instance restarts — that's acceptable.
"""
from collections import defaultdict
from config import MAX_HISTORY_MESSAGES, CHAT_MODEL

# Supported modes
MODES = {
    "chat": "💬 Chat Assistant",
    "code": "👨‍💻 Code Assistant",
    "doc":  "📄 Document Q&A",
    "image": "🖼️ Image Analysis",
}

DEFAULT_MODE = "chat"

# user_id -> {\"mode\": str, \"history\": list[dict], \"doc_text\": str|None, \"model\": str}
_sessions: dict[int, dict] = defaultdict(lambda: {
    "mode": DEFAULT_MODE,
    "history": [],
    "doc_text": None,
    "model": CHAT_MODEL,  # default model
})


def get_session(user_id: int) -> dict:
    return _sessions[user_id]


def set_mode(user_id: int, mode: str):
    _sessions[user_id]["mode"] = mode
    # Clear history on mode switch
    _sessions[user_id]["history"] = []
    _sessions[user_id]["doc_text"] = None


def get_mode(user_id: int) -> str:
    return _sessions[user_id]["mode"]


def add_message(user_id: int, role: str, content: str):
    history = _sessions[user_id]["history"]
    history.append({"role": role, "content": content})
    # Trim to keep only the last N messages
    if len(history) > MAX_HISTORY_MESSAGES:
        _sessions[user_id]["history"] = history[-MAX_HISTORY_MESSAGES:]


def get_history(user_id: int) -> list[dict]:
    return _sessions[user_id]["history"]


def set_doc_text(user_id: int, text: str):
    _sessions[user_id]["doc_text"] = text
    _sessions[user_id]["history"] = []  # reset Q&A history for new doc


def get_doc_text(user_id: int) -> str | None:
    return _sessions[user_id]["doc_text"]


def get_model(user_id: int) -> str:
    return _sessions[user_id]["model"]


def set_model(user_id: int, model: str):
    _sessions[user_id]["model"] = model
    _sessions[user_id]["history"] = []  # clear history on model switch


def clear_session(user_id: int):
    _sessions[user_id] = {
        "mode": DEFAULT_MODE,
        "history": [],
        "doc_text": None,
        "model": CHAT_MODEL,
    }
