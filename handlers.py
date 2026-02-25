"""
Telegram message/command handlers.
"""
import io
import asyncio
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import ContextTypes
from telegram.constants import ParseMode, ChatAction

import nvidia_client as ai
import session as sess
import file_modifier
from config import SELECTABLE_MODELS, ALLOWED_USER_IDS, AUTO_DELETE_DOC_AFTER_ANSWER, DOC_TTL_SECONDS

logger = logging.getLogger(__name__)


async def _keep_typing(bot, chat_id: int, stop_event: asyncio.Event):
    """Send typing action every 4 seconds until stop_event is set."""
    while not stop_event.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        except Exception:
            pass
        await asyncio.sleep(4)


def _is_allowed(user_id: int) -> bool:
    """Return True if user is allowed. If allowlist is empty, everyone is allowed."""
    if not ALLOWED_USER_IDS:
        return True
    return user_id in ALLOWED_USER_IDS


async def _check_allowed(update: Update) -> bool:
    """Check allowlist and send rejection if not allowed. Returns True if allowed."""
    if not _is_allowed(update.effective_user.id):
        await update.effective_message.reply_text(
            "⛔ Sorry, you are not authorized to use this bot.\n"
            "Contact the bot owner to request access."
        )
        return False
    return True

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


def _is_modification_request(text: str) -> bool:
    """Detect if the user wants to modify/edit the file rather than just ask about it."""
    keywords = [
        "modify", "edit", "change", "update", "add", "remove", "delete", "insert",
        "rename", "replace", "fix", "correct", "reformat", "convert", "transform",
        "sort", "filter", "calculate", "compute", "sum", "total", "average",
        "create", "generate", "make", "write", "save", "export", "download",
        "send", "give me", "provide", "produce", "output", "return",
        "append", "prepend", "merge", "split", "format", "clean", "fill",
    ]
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_allowed(update): return
    user = update.effective_user
    sess.clear_session(user.id)
    await update.message.reply_text(
        f"👋 Hello, {user.first_name}! I'm your NVIDIA AI-powered assistant.\n\n"
        "Just send me anything and I'll figure it out automatically:\n\n"
        "💬 *Chat* — Ask me anything\n"
        "👨‍💻 *Code* — Write, debug & explain code\n"
        "📄 *Files* — Send any PDF, Word, Excel, CSV, TXT... I'll read it!\n"
        "🖼️ *Images* — Send any photo and I'll analyze it!\n\n"
        "No need to switch modes — I detect what you send automatically.\n"
        "Use /mode to manually set a mode, or just start sending! 🚀",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_allowed(update): return
    current = sess.get_mode(update.effective_user.id)
    await update.message.reply_text(
        f"Current mode: *{_mode_label(current)}*\n\nSwitch to:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_mode_keyboard(),
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_allowed(update): return
    user_id = update.effective_user.id
    sess.clear_session(user_id)
    await update.message.reply_text(
        "🗑️ All data cleared — conversation history, documents, and session reset!"
    )


async def cmd_privacy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_allowed(update): return
    user_id = update.effective_user.id
    info = sess.get_privacy_info(user_id)

    ttl_mins = DOC_TTL_SECONDS // 60
    doc_status = "None"
    if info["has_doc"]:
        expires_mins = (info["doc_expires_in"] or 0) // 60
        doc_status = f"✅ *{info['doc_name']}* (expires in ~{expires_mins} min)"

    history_note = (
        f"{info['history_count']} messages in memory"
        if info["history_count"] > 0
        else "No messages stored"
    )

    await update.message.reply_text(
        "🔒 *Your Privacy & Data Summary*\n\n"
        f"*Current mode:* {sess.MODES.get(info['mode'], info['mode'])}\n"
        f"*AI model:* `{info['model']}`\n"
        f"*Conversation:* {history_note}\n"
        f"*Document:* {doc_status}\n\n"
        "📋 *What we store (in RAM only):*\n"
        "• Your conversation history (last 20 messages)\n"
        "• Uploaded document text (auto-deleted after "
        f"{ttl_mins} min)\n"
        "• Your selected mode & model\n\n"
        "📋 *What we DON'T store:*\n"
        "• Files on disk (everything is in RAM)\n"
        "• Your Telegram messages permanently\n"
        "• Any data after bot restarts\n\n"
        "⚠️ *Note:* Document text is sent to NVIDIA's API for processing.\n\n"
        "🗑️ Use /clear to delete all your data immediately.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_allowed(update): return
    await update.message.reply_text(
        "🤖 *NVIDIA AI Telegram Bot — Help*\n\n"
        "🪄 *Auto-detection:* Just send anything — no mode switching needed!\n"
        "• Send a *photo* → auto image analysis\n"
        "• Send a *file* → auto document Q&A\n"
        "• Send *text* → chat (or doc Q&A if a file is loaded)\n\n"
        "*Commands:*\n"
        "/start — Welcome message\n"
        "/mode — Manually set a mode (chat/code/doc/image)\n"
        "/model — Switch the AI model\n"
        "/clear — Clear all your data\n"
        "/privacy — View & manage your stored data\n"
        "/help — Show this help message\n\n"
        "*Supported file types:*\n"
        "PDF, Word (.docx), Excel (.xlsx), CSV, JSON, TXT, MD, PY and more\n\n"
        "*Tips:*\n"
        "• Bot remembers your last 20 messages\n"
        "• Ask to *modify* a file → bot sends back the edited file!\n"
        "• Use /clear to reset everything\n"
        "• Use /model to switch AI models anytime",
        parse_mode=ParseMode.MARKDOWN,
    )


def _model_keyboard():
    buttons = []
    for key, (model_id, label) in SELECTABLE_MODELS.items():
        buttons.append([InlineKeyboardButton(label, callback_data=f"model_{key}")])
    return InlineKeyboardMarkup(buttons)


async def cmd_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    current_model = sess.get_model(user_id)
    # Find current model label
    current_label = current_model
    for key, (model_id, label) in SELECTABLE_MODELS.items():
        if model_id == current_model:
            current_label = label
            break
    await update.message.reply_text(
        f"🧠 *Current model:* `{current_label}`\n\n"
        "Choose a model to switch to:\n"
        "_(Note: Image Analysis always uses the vision model regardless of this setting)_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=_model_keyboard(),
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
        "doc":   "Upload a file and I'll answer questions about it.\n📄 Supported: PDF, Word (.docx), Excel (.xlsx), CSV, JSON, TXT, MD, PY, and more!",
        "image": "Send me a photo (with an optional caption/question) and I'll analyze it.",
    }

    await query.edit_message_text(
        f"✅ Switched to *{label}* mode.\n\n{instructions[mode]}\n\n"
        "Use /mode to switch anytime, /clear to reset history.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def callback_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    key = query.data.replace("model_", "")

    if key not in SELECTABLE_MODELS:
        return

    model_id, label = SELECTABLE_MODELS[key]
    sess.set_model(user_id, model_id)

    await query.edit_message_text(
        f"✅ Switched to *{label}*\n\n"
        f"`{model_id}`\n\n"
        "Conversation history cleared. Start chatting!",
        parse_mode=ParseMode.MARKDOWN,
    )


# ---------------------------------------------------------------------------
# Text messages
# ---------------------------------------------------------------------------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_allowed(update): return
    user_id = update.effective_user.id
    mode = sess.get_mode(user_id)
    user_text = update.message.text.strip()

    if not user_text:
        return

    # Send immediate feedback
    thinking_msg: Message = await update.message.reply_text("⏳ Thinking...")

    # Start persistent typing indicator in background
    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(
        _keep_typing(context.bot, update.effective_chat.id, stop_typing)
    )

    sess.add_message(user_id, "user", user_text)
    history = sess.get_history(user_id)
    model = sess.get_model(user_id)

    # --- AUTO-MODE DETECTION ---
    # Priority: manual mode override > doc in memory > code detection > chat
    doc_text = sess.get_doc_text(user_id)

    # Determine effective mode
    if mode in ("chat", "image"):
        # If a doc is loaded and user is in chat/image mode, auto-switch to doc Q&A
        effective_mode = "doc" if doc_text else mode
    else:
        effective_mode = mode  # respect explicit code/doc mode

    try:
        if effective_mode == "doc" and doc_text:
            # Check if user wants to modify the file
            if _is_modification_request(user_text):
                file_bytes, file_name, file_mime = sess.get_doc_file(user_id)
                if file_bytes:
                    await thinking_msg.edit_text("⚙️ Modifying your file, please wait...")
                    output_bytes, output_filename, error = file_modifier.modify_file(
                        doc_text=doc_text,
                        file_bytes=file_bytes,
                        filename=file_name or "document",
                        user_request=user_text,
                        model=model,
                    )
                    stop_typing.set()
                    typing_task.cancel()
                    if error:
                        reply = f"⚠️ Could not modify the file:\n`{error[:500]}`"
                        await thinking_msg.edit_text(reply, parse_mode=ParseMode.MARKDOWN)
                    else:
                        await thinking_msg.edit_text("✅ File modified! Sending it now...")
                        await update.message.reply_document(
                            document=io.BytesIO(output_bytes),
                            filename=output_filename,
                            caption=f"✅ Here's your modified file: *{output_filename}*",
                            parse_mode=ParseMode.MARKDOWN,
                        )
                    sess.add_message(user_id, "user", user_text)
                    sess.add_message(user_id, "assistant",
                                     f"[Modified file sent: {output_filename}]" if not error else reply)
                    return
            reply = ai.document_qa(doc_text, history, model=model)
            if AUTO_DELETE_DOC_AFTER_ANSWER:
                sess.clear_doc(user_id)

        elif effective_mode == "code":
            reply = ai.code_assist(history, model=model)

        elif effective_mode == "image":
            stop_typing.set()
            typing_task.cancel()
            reply = "🖼️ Please send a photo and I'll analyze it for you!"
            sess.add_message(user_id, "assistant", reply)
            await thinking_msg.edit_text(reply)
            return

        else:
            reply = ai.chat(history, model=model)

    except Exception as e:
        logger.error(f"NVIDIA API error: {e}")
        stop_typing.set()
        typing_task.cancel()
        reply = f"⚠️ Sorry, I ran into an error talking to the AI:\n`{e}`"
        await thinking_msg.edit_text(reply, parse_mode=ParseMode.MARKDOWN)
        return

    finally:
        stop_typing.set()
        typing_task.cancel()

    sess.add_message(user_id, "assistant", reply)

    # Edit the "Thinking..." message with the first chunk, send rest as new messages
    MAX = 4000
    chunks = [reply[i:i+MAX] for i in range(0, len(reply), MAX)]
    await thinking_msg.edit_text(chunks[0])
    for chunk in chunks[1:]:
        await update.message.reply_text(chunk)


# ---------------------------------------------------------------------------
# Photo messages
# ---------------------------------------------------------------------------

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_allowed(update): return
    user_id = update.effective_user.id

    # Auto-mode: always analyze photos regardless of current mode
    thinking_msg: Message = await update.message.reply_text("⏳ Analyzing image...")

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(
        _keep_typing(context.bot, update.effective_chat.id, stop_typing)
    )

    # Get highest resolution photo
    photo = update.message.photo[-1]
    caption = update.message.caption or ""

    try:
        file = await context.bot.get_file(photo.file_id)
        file_bytes = bytes(await file.download_as_bytearray())
        mime_type = "image/jpeg"  # Telegram photos are always JPEG

        history = sess.get_history(user_id)
        reply = ai.image_analysis(file_bytes, mime_type, caption, history)

        # Log image interaction in history as text
        user_entry = f"[User sent an image{': ' + caption if caption else ''}]"
        sess.add_message(user_id, "user", user_entry)
        sess.add_message(user_id, "assistant", reply)

        MAX = 4000
        chunks = [reply[i:i+MAX] for i in range(0, len(reply), MAX)]
        await thinking_msg.edit_text(chunks[0])
        for chunk in chunks[1:]:
            await update.message.reply_text(chunk)

    except Exception as e:
        logger.error(f"Image analysis error: {e}")
        await thinking_msg.edit_text(
            f"⚠️ Error analyzing the image:\n`{e}`",
            parse_mode=ParseMode.MARKDOWN,
        )
    finally:
        stop_typing.set()
        typing_task.cancel()


# ---------------------------------------------------------------------------
# Document messages
# ---------------------------------------------------------------------------

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_allowed(update): return
    user_id = update.effective_user.id

    # Auto-mode: always process documents regardless of current mode
    thinking_msg: Message = await update.message.reply_text("⏳ Processing document...")

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(
        _keep_typing(context.bot, update.effective_chat.id, stop_typing)
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
            await thinking_msg.edit_text(
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

        sess.set_doc_text(user_id, text, filename=file_name, file_bytes=bytes(file_bytes), mime=mime)
        word_count = len(text.split())
        await thinking_msg.edit_text(
            f"✅ *{file_name}* loaded successfully!\n"
            f"📊 ~{word_count:,} words extracted.\n\n"
            "Now ask me anything about it!",
            parse_mode=ParseMode.MARKDOWN,
        )

    except Exception as e:
        logger.error(f"Document processing error: {e}")
        await thinking_msg.edit_text(
            f"⚠️ Error processing the document:\n`{e}`",
            parse_mode=ParseMode.MARKDOWN,
        )
    finally:
        stop_typing.set()
        typing_task.cancel()


def _extract_text(data: bytes, filename: str, mime: str) -> str:
    """Extract plain text from file bytes. Supports txt, pdf, docx, xlsx, csv, json, md, py, etc."""
    fname_lower = filename.lower()

    # PDF
    if fname_lower.endswith(".pdf") or "pdf" in mime:
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(data))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n\n".join(p for p in pages if p.strip())
        except Exception as e:
            return f"[PDF extraction error: {e}]"

    # Word (.docx)
    if fname_lower.endswith(".docx") or "wordprocessingml" in mime or "msword" in mime:
        try:
            import docx
            doc = docx.Document(io.BytesIO(data))
            parts = []
            for para in doc.paragraphs:
                if para.text.strip():
                    parts.append(para.text)
            # Also extract tables
            for table in doc.tables:
                for row in table.rows:
                    parts.append("\t".join(cell.text for cell in row.cells))
            return "\n".join(parts)
        except Exception as e:
            return f"[Word extraction error: {e}]"

    # Excel (.xlsx, .xls)
    if fname_lower.endswith((".xlsx", ".xls")) or "spreadsheet" in mime or "excel" in mime:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            parts = []
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                parts.append(f"=== Sheet: {sheet_name} ===")
                for row in ws.iter_rows(values_only=True):
                    row_str = "\t".join(str(c) if c is not None else "" for c in row)
                    if row_str.strip():
                        parts.append(row_str)
            return "\n".join(parts)
        except Exception as e:
            return f"[Excel extraction error: {e}]"

    # CSV — decode as text
    if fname_lower.endswith(".csv") or "csv" in mime:
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data.decode("latin-1", errors="replace")

    # JSON — decode and pretty print
    if fname_lower.endswith(".json") or "json" in mime:
        try:
            import json
            parsed = json.loads(data.decode("utf-8"))
            return json.dumps(parsed, indent=2, ensure_ascii=False)
        except Exception:
            return data.decode("utf-8", errors="replace")

    # Everything else: plain text (py, md, txt, html, yaml, toml, etc.)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return data.decode("latin-1")
        except Exception:
            return "[Could not extract text from this file type.]"
