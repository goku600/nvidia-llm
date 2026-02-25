"""
In-memory session store for per-user conversation history and mode tracking.
On Render free tier, memory is reset when the instance restarts — that's acceptable.

Privacy features:
- Document text is stored with a TTL (auto-expires after DOC_TTL_SECONDS)
- Documents can be auto-deleted after answering a question
- Users can clear all their data with /clear or /privacy
"""
import time
from collections import defaultdict
from config import MAX_HISTORY_MESSAGES, CHAT_MODEL, DOC_TTL_SECONDS

# Supported modes
MODES = {
    "chat":  "💬 Chat Assistant",
    "code":  "👨‍💻 Code Assistant",
    "doc":   "📄 Document Q&A",
    "image": "🖼️ Image Analysis",
}

DEFAULT_MODE = "chat"

# user_id -> {
#   "mode": str,
#   "history": list[dict],
#   "doc_text": str|None,
#   "doc_name": str|None,
#   "doc_uploaded_at": float|None,   # unix timestamp
#   "model": str,
#   "started_at": float,             # unix timestamp when session started
# }
_sessions: dict[int, dict] = defaultdict(lambda: {
    "mode": DEFAULT_MODE,
    "history": [],
    "doc_text": None,
    "doc_name": None,
    "doc_uploaded_at": None,
    "model": CHAT_MODEL,
    "started_at": time.time(),
})


def get_session(user_id: int) -> dict:
    return _sessions[user_id]


def set_mode(user_id: int, mode: str):
    _sessions[user_id]["mode"] = mode
    _sessions[user_id]["history"] = []
    _sessions[user_id]["doc_text"] = None
    _sessions[user_id]["doc_name"] = None
    _sessions[user_id]["doc_uploaded_at"] = None


def get_mode(user_id: int) -> str:
    return _sessions[user_id]["mode"]


def add_message(user_id: int, role: str, content: str):
    history = _sessions[user_id]["history"]
    history.append({"role": role, "content": content})
    if len(history) > MAX_HISTORY_MESSAGES:
        _sessions[user_id]["history"] = history[-MAX_HISTORY_MESSAGES:]


def get_history(user_id: int) -> list[dict]:
    return _sessions[user_id]["history"]


def set_doc_text(user_id: int, text: str, filename: str = "document",
                 file_bytes: bytes | None = None, mime: str | None = None):
    _sessions[user_id]["doc_text"] = text
    _sessions[user_id]["doc_name"] = filename
    _sessions[user_id]["doc_bytes"] = file_bytes   # original raw bytes
    _sessions[user_id]["doc_mime"] = mime
    _sessions[user_id]["doc_uploaded_at"] = time.time()
    _sessions[user_id]["history"] = []  # reset Q&A history for new doc


def get_doc_file(user_id: int) -> tuple[bytes | None, str | None, str | None]:
    """Return (file_bytes, filename, mime) for the stored document."""
    s = _sessions[user_id]
    return s.get("doc_bytes"), s.get("doc_name"), s.get("doc_mime")


def get_doc_text(user_id: int) -> str | None:
    """Return doc text if not expired, else auto-clear and return None."""
    session = _sessions[user_id]
    if session["doc_text"] is None:
        return None
    uploaded_at = session.get("doc_uploaded_at")
    if uploaded_at and (time.time() - uploaded_at) > DOC_TTL_SECONDS:
        # TTL expired — auto-clear
        session["doc_text"] = None
        session["doc_name"] = None
        session["doc_uploaded_at"] = None
        session["history"] = []
        return None
    return session["doc_text"]


def clear_doc(user_id: int):
    """Wipe only the document from memory."""
    _sessions[user_id]["doc_text"] = None
    _sessions[user_id]["doc_name"] = None
    _sessions[user_id]["doc_bytes"] = None
    _sessions[user_id]["doc_mime"] = None
    _sessions[user_id]["doc_uploaded_at"] = None
    _sessions[user_id]["history"] = []


def get_model(user_id: int) -> str:
    return _sessions[user_id]["model"]


def set_model(user_id: int, model: str):
    _sessions[user_id]["model"] = model
    _sessions[user_id]["history"] = []


def get_privacy_info(user_id: int) -> dict:
    """Return a summary of what data is stored for this user."""
    session = _sessions[user_id]
    doc_uploaded_at = session.get("doc_uploaded_at")
    doc_expires_in = None
    if doc_uploaded_at:
        remaining = DOC_TTL_SECONDS - (time.time() - doc_uploaded_at)
        doc_expires_in = max(0, int(remaining))

    return {
        "mode": session["mode"],
        "model": session["model"],
        "history_count": len(session["history"]),
        "has_doc": session["doc_text"] is not None,
        "doc_name": session.get("doc_name"),
        "doc_expires_in": doc_expires_in,
        "session_started": session.get("started_at"),
    }


def clear_session(user_id: int):
    _sessions[user_id] = {
        "mode": DEFAULT_MODE,
        "history": [],
        "doc_text": None,
        "doc_name": None,
        "doc_bytes": None,
        "doc_mime": None,
        "doc_uploaded_at": None,
        "model": CHAT_MODEL,
        "started_at": time.time(),
    }
