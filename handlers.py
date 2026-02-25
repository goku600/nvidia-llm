"""
Telegram message/command handlers.
"""
import io
import base64
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode, ChatAction

import nvidia_client as ai
import session as sess

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mode_keyboard():
    buttons = [
        [InlineKeyboardButton("💬 Chat Assistant", callback_data="mode_chat"),
         InlineKeyboardButton("👨‍💻 Code Assistant", callback_data="mode_code")],
        [InlineKeyboardButton("📄 Document Q&A", callback_data="mode_doc"),
         InlineKeyboardButton("🖼️ Image Analysis", callback_data="mode_image")],
    ]
    return InlineKeyboardMarkup(buttons)


def _mode_label(mode: str) -> str:
    return sess.MODES.get(mode, mode)


async def _send_long(update: Update, text: str):
    """Send text, splitting into chunks if it exceeds Telegram's 4096 char limit."""
    MAX = 4000
    if len(text) <= MAX:
        await update.effective_message.reply_text(text)
        return
    chunks = [text[i:i+MAX] for i in range(0, len(text), MAX)]
    for chunk in chunks:
        await update.effective_message.reply_text(chunk)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    sess.clear_session(user.id)
    await update.message.reply_text(
        f"👋 Hello, {user.first_name}! I'm your NVIDIA AI-powered assistant.\n\n"
        "I can do all of the following:\n"
        "💬 *Chat* — General conversation & questions\n"
        "👨‍💻 *Code* — Write, debug & explain code\n"
        "📄 *Document Q&A* — Upload a file and ask questions\n"
        "🖼️ *Image Analysis* — Send a photo and ask about it\n\n"
        "Choose a mode to get started:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_mode_keyboard(),
    )


async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current = sess.get_mode(update.effective_user.id)
    await update.message.reply_text(
        f"Current mode: *{_mode_label(current)}*\n\nSwitch to:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_mode_keyboard(),
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mode = sess.get_mode(user_id)
    sess.set_mode(user_id, mode)  # keeps mode, clears history & doc
    await update.message.reply_text(
        "🗑️ Conversation history cleared. Ready for a fresh start!"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *NVIDIA AI Telegram Bot — Help*\n\n"
        "*Commands:*\n"
        "/start — Welcome message & mode picker\n"
        "/mode — Switch between assistant modes\n"
        "/clear — Clear conversation history\n"
        "/help — Show this help message\n\n"
        "*Modes:*\n"
        "💬 *Chat* — Ask anything, have a conversation\n"
        "👨‍💻 *Code* — Get help with programming\n"
        "📄 *Doc Q&A* — Upload .txt/.pdf/.py etc., then ask questions\n"
        "🖼️ *Image* — Send a photo (+ optional caption) for analysis\n\n"
        "*Tips:*\n"
        "• The bot remembers your last 20 messages per mode\n"
        "• Use /clear to reset the conversation\n"
        "• Use /mode to switch modes anytime",
        parse_mode=ParseMode.MARKDOWN,
    )


# ---------------------------------------------------------------------------
# Callback: mode selection buttons
# ---------------------------------------------------------------------------

async def callback_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    mode = query.data.replace("mode_", "")

    if mode not in sess.MODES:
        return

    sess.set_mode(user_id, mode)
    label = _mode_label(mode)

    instructions = {
        "chat":  "Just send me a message and we'll chat! I remember the conversation context.",
        "code":  "Send me code to review/debug, describe what you want to build, or ask any programming question.",
        "doc":   "Upload a document (.txt, .pdf, .py, .md, .csv, etc.) and I'll answer questions about it.",
        "image": "Send me a photo (with an optional caption/question) and I'll analyze it.",
    }

    await query.edit_message_text(
        f"✅ Switched to *{label}* mode.\n\n{instructions[mode]}\n\n"
        "Use /mode to switch anytime, /clear to reset history.",
        parse_mode=ParseMode.MARKDOWN,
    )


# ---------------------------------------------------------------------------
# Text messages
# ---------------------------------------------------------------------------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mode = sess.get_mode(user_id)
    user_text = update.message.text.strip()

    if not user_text:
        return

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )

    sess.add_message(user_id, "user", user_text)
    history = sess.get_history(user_id)

    try:
        if mode == "chat":
            reply = ai.chat(history)

        elif mode == "code":
            reply = ai.code_assist(history)

        elif mode == "doc":
            doc_text = sess.get_doc_text(user_id)
            if not doc_text:
                reply = (
                    "📄 You're in *Document Q&A* mode but haven't uploaded a document yet.\n"
                    "Please upload a file first (.txt, .pdf, .py, .md, etc.)."
                )
                sess.add_message(user_id, "assistant", reply)
                await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)
                return
            reply = ai.document_qa(doc_text, history)

        elif mode == "image":
            reply = (
                "🖼️ You're in *Image Analysis* mode.\n"
                "Please send a photo (you can add a caption with your question)."
            )
            sess.add_message(user_id, "assistant", reply)
            await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)
            return

        else:
            reply = ai.chat(history)

    except Exception as e:
        logger.error(f"NVIDIA API error: {e}")
        reply = f"⚠️ Sorry, I ran into an error talking to the AI:\n`{e}`"
        await update.message.reply_text(reply, parse_mode=ParseMode.MARKDOWN)
        return

    sess.add_message(user_id, "assistant", reply)
    await _send_long(update, reply)


# ---------------------------------------------------------------------------
# Photo messages
# ---------------------------------------------------------------------------

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mode = sess.get_mode(user_id)

    if mode != "image":
        await update.message.reply_text(
            f"📷 I received a photo, but you're in *{_mode_label(mode)}* mode.\n"
            "Switch to 🖼️ *Image Analysis* mode via /mode to analyze images.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )

    # Get highest resolution photo
    photo = update.message.photo[-1]
    caption = update.message.caption or ""

    try:
        file = await context.bot.get_file(photo.file_id)
        file_bytes = await file.download_as_bytearray()
        image_b64 = base64.b64encode(bytes(file_bytes)).decode()
        mime_type = "image/jpeg"  # Telegram photos are always JPEG

        history = sess.get_history(user_id)
        reply = ai.image_analysis(image_b64, mime_type, caption, history)

        # Log image interaction in history as text
        user_entry = f"[User sent an image{': ' + caption if caption else ''}]"
        sess.add_message(user_id, "user", user_entry)
        sess.add_message(user_id, "assistant", reply)

        await _send_long(update, reply)

    except Exception as e:
        logger.error(f"Image analysis error: {e}")
        await update.message.reply_text(
            f"⚠️ Error analyzing the image:\n`{e}`",
            parse_mode=ParseMode.MARKDOWN,
        )


# ---------------------------------------------------------------------------
# Document messages
# ---------------------------------------------------------------------------

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mode = sess.get_mode(user_id)

    if mode != "doc":
        await update.message.reply_text(
            f"📎 I received a file, but you're in *{_mode_label(mode)}* mode.\n"
            "Switch to 📄 *Document Q&A* mode via /mode to analyze documents.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.TYPING
    )

    doc = update.message.document
    file_name = doc.file_name or "document"
    mime = doc.mime_type or ""

    try:
        file = await context.bot.get_file(doc.file_id)
        file_bytes = await file.download_as_bytearray()

        # Extract text based on file type
        text = _extract_text(bytes(file_bytes), file_name, mime)

        if not text.strip():
            await update.message.reply_text(
                "⚠️ I couldn't extract any text from that file. "
                "Please try a plain text file (.txt, .md, .py, .csv, .json, etc.)."
            )
            return

        # Limit document size (approx 100k chars to fit in context)
        MAX_DOC_CHARS = 100_000
        if len(text) > MAX_DOC_CHARS:
            text = text[:MAX_DOC_CHARS]
            await update.message.reply_text(
                f"⚠️ Document is large — I'll use the first {MAX_DOC_CHARS:,} characters."
            )

        sess.set_doc_text(user_id, text)
        word_count = len(text.split())
        await update.message.reply_text(
            f"✅ Document *{file_name}* loaded successfully!\n"
            f"📊 ~{word_count:,} words extracted.\n\n"
            "Now ask me anything about it!",
            parse_mode=ParseMode.MARKDOWN,
        )

    except Exception as e:
        logger.error(f"Document processing error: {e}")
        await update.message.reply_text(
            f"⚠️ Error processing the document:\n`{e}`",
            parse_mode=ParseMode.MARKDOWN,
        )


def _extract_text(data: bytes, filename: str, mime: str) -> str:
    """Extract plain text from file bytes. Supports txt, pdf, and common text formats."""
    fname_lower = filename.lower()

    # PDF extraction
    if fname_lower.endswith(".pdf") or "pdf" in mime:
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(data))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except ImportError:
            return "[pypdf not installed — PDF support unavailable. Use .txt files.]"
        except Exception as e:
            return f"[PDF extraction error: {e}]"

    # Everything else: try to decode as UTF-8 text
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return data.decode("latin-1")
        except Exception:
            return ""
