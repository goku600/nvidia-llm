import requests
import json
import base64
from config import (
    NVIDIA_API_KEY, NVIDIA_API_URL,
    MAX_TOKENS, TEMPERATURE, TOP_P, TOP_K,
    CHAT_MODEL, VISION_MODEL, CODE_MODEL, DOC_MODEL
)



def _build_headers(stream: bool = False):
    return {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Accept": "text/event-stream" if stream else "application/json",
    }


import aiohttp
from typing import AsyncGenerator

async def _post(payload: dict):
    """Send a streaming request to NVIDIA API and yield text chunks."""
    payload = {**payload, "stream": True}
    headers = _build_headers(stream=True)
    timeout = aiohttp.ClientTimeout(total=300, connect=10)
    
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(NVIDIA_API_URL, headers=headers, json=payload) as response:
            response.raise_for_status()
            
            async for line in response.content:
                if not line:
                    continue
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError) as e:
                        import logging
                        logging.getLogger(__name__).warning(f"Failed to parse NVIDIA API chunk: '{data_str}' -> Error: {e}")
                        continue


def _base_payload(model: str, messages: list, thinking: bool = False) -> dict:
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "top_k": TOP_K,
        "presence_penalty": 0,
        "repetition_penalty": 1,
        "stream": True,
    }
    if thinking:
        payload["chat_template_kwargs"] = {"enable_thinking": True}
    return payload


# ---------------------------------------------------------------------------
# Unified Omni-Modal Chat
# ---------------------------------------------------------------------------

async def chat(history: list[dict], model: str = CHAT_MODEL) -> AsyncGenerator[str, None]:
    """
    history: list of {"role": "user"|"assistant"|"system", "content": str}
    Yields chunks of the assistant's reply.
    """
    system_prompt = (
        "You are an expert NVIDIA AI Assistant, a unified omni-modal AI. "
        "You help users with general chat, coding, data analysis, and document Q&A seamlessly. "
        "The user may upload images or documents, which will appear in the chat history.\n\n"
        "*** ADVANCED CAPABILITY: FILE GENERATION & MODIFICATION ***\n"
        "You have the ability to execute Python code in a secure sandbox to generate or modify files "
        "if the user explicitly asks for a file to be returned, modified, converted, or exported.\n\n"
        "When the user asks you to create a file (e.g., 'generate an excel file', 'give me a pdf'), "
        "or edit an existing one, you MUST output the exact Python code needed to do it inside "
        "a special `[PYTHON_EXEC]` block.\n\n"
        "RULES FOR `[PYTHON_EXEC]`:\n"
        "1. Start the block with exactly `[PYTHON_EXEC]` on its own line.\n"
        "2. End the block with exactly `[/PYTHON_EXEC]` on its own line.\n"
        "3. Allowed libraries: io, json, csv, re, math, datetime, collections, openpyxl, pypdf, docx, PIL, reportlab, requests, urllib, gspread, pandas, numpy.\n"
        "4. **No other imports** or local disk access is allowed. You MAY use 'requests' or 'urllib' to download internet data or images if requested. ALWAYS use a User-Agent and check `raise_for_status()` to avoid downloading error pages. Write successful downloaded content directly to `output_buffer`. DO NOT hallucinate URLs. You MUST use the `[WEB_SEARCH]` tool first to find a real, valid URL to the requested image or data before writing code. DO NOT import 'Link' from reportlab.platypus and DO NOT import 'getNormalStyle' from reportlab.lib.styles. For Google Sheets (often called 'database' or 'docs database' by the user), you have a globally defined authenticated client named `gspread_client`. Just do `sheet = gspread_client.open('Sheet Name').sheet1`. Use `sheet.append_row()` to add data. Use `sheet.update()`, `sheet.delete_rows()` ONLY if asked to overwrite or remove. If asked to 'read' or 'show' database data, you MUST pull all records (`data = sheet.get_all_records()`), convert to a pandas DataFrame (`df = pandas.DataFrame(data)`), and save it to the `output_buffer` as a CSV (`df.to_csv(output_buffer, index=False)`) or string TXT file so the user can download it. To add hyperlinks, use the formula format: `=HYPERLINK(\"url\", \"text\")`.\n"
        "5. If a user previously uploaded a document, its raw bytes are available in the variable `input_bytes` (type: bytes).\n"
        "6. Write your output to the pre-existing variable `output_buffer` (type: io.BytesIO). DO NOT use `open()` to save files, as it is strictly blocked. If loading an internet image into PIL, you MUST verify it succeeds and wrap the bytes: `Image.open(io.BytesIO(r.content))`.\n"
        "7. Set the pre-existing variable `output_filename` (type: str) to the desired filename.\n\n"
        "EXAMPLE (User: 'Create a PDF with a long essay'):\n"
        "Sure, I'll generate that PDF for you right now.\n"
        "[PYTHON_EXEC]\n"
        "from reportlab.platypus import SimpleDocTemplate, Paragraph\n"
        "from reportlab.lib.styles import getSampleStyleSheet\n"
        "doc = SimpleDocTemplate(output_buffer)\n"
        "styles = getSampleStyleSheet()\n"
        "flowables = [Paragraph('This is a very long essay that will automatically wrap to the next line...', styles['Normal'])]\n"
        "doc.build(flowables)\n"
        "output_filename = 'essay.pdf'\n"
        "[/PYTHON_EXEC]\n\n"
        "*** ADVANCED CAPABILITY: WEB SEARCH ***\n"
        "You have access to a real-time web search tool. Your internal knowledge cutoff is around late 2023.\n"
        "Whenever the user asks you about current events (e.g., 'Who is the PM in 2026?'), recent news, prices, weather, "
        "or facts you are unsure about, you MUST search the web.\n"
        "CRITICALLY: If you are asked to write a Python script using a library (like reportlab, python-docx, etc.) and you "
        "are NOT 100% sure about the exact function names or classes, you MUST search the web for the official documentation "
        "or examples BEFORE writing the `[PYTHON_EXEC]` block to avoid hallucinated imports. Furthermore, if you need to download an image or file via Python, you MUST search the web to find a direct, valid URL first (e.g. ending in .jpg or .png) to avoid hallucinating fake links or using unreliable redirect APIs like source.unsplash.com.\n"
        "To perform a search, output exactly this block and IMMEDIATELY STOP GENERATING:\n"
        "[WEB_SEARCH] your search query here [/WEB_SEARCH]\n"
        "CRITICAL: Do NEVER output a `[PYTHON_EXEC]` block in the same response as a `[WEB_SEARCH]`. You MUST wait for the system to provide the search results first!\n\n"
        "The system will execute the query and provide you with snippets from DuckDuckGo. You will then automatically "
        "continue the conversation and provide the final answer based on those snippets.\n"
        "EXAMPLE (User: 'What is NVIDIA stock price today?'):\n"
        "Let me look up the latest price for you.\n"
        "[WEB_SEARCH] NVIDIA NVDA stock price today [/WEB_SEARCH]\n"
    )

    # Ensure system prompt is first. If the first message in history is already a system prompt
    # (e.g. from an uploaded doc), we prepend a dedicated system message.
    messages = [{"role": "system", "content": system_prompt}] + history
    payload = _base_payload(model, messages)
    
    async for chunk in _post(payload):
        yield chunk


# ---------------------------------------------------------------------------
# Image Analysis
# ---------------------------------------------------------------------------

async def image_analysis(image_bytes: bytes, mime_type: str, user_prompt: str, history: list[dict]) -> AsyncGenerator[str, None]:
    """
    image_bytes: raw image bytes
    mime_type: e.g. "image/jpeg", "image/png"
    user_prompt: the user's question about the image
    history: previous turns (without the current image message)
    """
    prompt = user_prompt if user_prompt else "Describe this image in detail."
    image_b64 = base64.b64encode(image_bytes).decode()

    current_message = {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": prompt,
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime_type};base64,{image_b64}"
                },
            },
        ],
    }

    # For vision, include past text history + current image message
    text_history = [msg for msg in history if isinstance(msg.get("content"), str)]
    messages = text_history + [current_message]

    payload = _base_payload(VISION_MODEL, messages)
    
    async for chunk in _post(payload):
        yield chunk
