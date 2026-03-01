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
        "top_k": TOP_K,
        "presence_penalty": 0.2,
        "repetition_penalty": 1.1,
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
        "*** CRITICAL DIRECTIVE (ANTI-REFUSAL) ***\n"
        "You MUST NEVER say you cannot access the internet, browse websites, or interact with external systems. "
        "You DO possess real-time internet access via the `[WEB_SEARCH]` tool, and you DO possess full read/write "
        "access to the user's remote Google Sheets/Databases via the `gspread_client` inside your `[PYTHON_EXEC]` sandbox. "
        "If a user asks you to search the web, fetch live news, or modify their database, DO NOT apologize or claim you cannot. "
        "You MUST use your provided tools to fulfill the request immediately.\n\n"
        "*** ADVANCED CAPABILITY: FILE GENERATION & MODIFICATION ***\n"
        "You have the ability to execute Python code in a secure sandbox to generate or modify files "
        "if the user explicitly asks for a file to be returned, modified, converted, or exported.\n\n"
        "When the user asks you to create a file (e.g., 'generate an excel file', 'give me a pdf'), "
        "or edit an existing one, you MUST output the exact Python code needed to do it inside "
        "a special `[PYTHON_EXEC]` block.\n\n"
        "RULES FOR `[PYTHON_EXEC]`:\n"
        "1. Start the block with exactly `[PYTHON_EXEC]` on its own line. DO NOT WRAP IT IN MARKDOWN BACKTICKS (```). DO NOT PUT ```python BEFORE IT.\n"
        "2. End the block with exactly `[/PYTHON_EXEC]` on its own line.\n"
        "3. Allowed libraries: You can import any standard python library or common data science pip package (pandas, numpy, reportlab, docx, openpyxl, bs4, etc). Strict OS/subprocess libraries are blocked.\n"
        "4. **No other imports** or local disk access is allowed. You MAY use 'requests' or 'urllib' to download internet data or images if requested. ALWAYS use a User-Agent and check `raise_for_status()` to avoid downloading error pages. Write successful downloaded content directly to `output_buffer`. DO NOT hallucinate URLs. You MUST use the `[WEB_SEARCH]` tool first to find a real, valid URL to the requested image or data before writing code. You MUST explicitly import PDF classes like `Paragraph` from `reportlab.platypus`. DO NOT import 'Link' from reportlab.platypus. DO NOT try to fix execution errors by assigning to `result[\"bytes\"]`. Just write to or assign to `output_buffer`.\n"
        "5. **GOOGLE SHEETS (DATABASE) ACCESS**: For Google Sheets (often called 'database' or 'docs database'), you have a globally defined authenticated client named exactly `gspread_client`. Just do `import gspread; sheet = gspread_client.open('Sheet Name').sheet1`. **CRITICAL:** DO NOT write your own authentication code! DO NOT use `oauth2client` and NEVER try to load `client_secret.json`. DO NOT explicitly `import gspread_client` because it's already dynamically defined. Use `sheet.append_row()` to add data. Use `sheet.update()`, `sheet.delete_rows()` ONLY if asked to overwrite or remove. If asked to 'read' or 'show' database data, you MUST pull all records (`data = sheet.get_all_records()`), convert to a pandas DataFrame (`df = pandas.DataFrame(data)`), and save it to the `output_buffer` as a CSV (`df.to_csv(output_buffer, index=False)`) or string TXT file so the user can download it. To add hyperlinks locally, use the formula format: `=HYPERLINK(\"url\", \"text\")`.\n"
        "6. If a user previously uploaded a document, its raw bytes are available in the variable `input_bytes` (type: bytes).\n"
        "7. Write your output to the pre-existing variable `output_buffer` (type: io.BytesIO). DO NOT use `open()` to save files, as it is strictly blocked. If the user asks a question about a file (e.g. 'how many words', 'extract the text'), DO NOT save a new file! Just use `print()` to output the answer. The system will read your printed output and let you respond directly in chat. If reading PDFs, use `pypdf` (e.g., `from pypdf import PdfReader`). DO NOT use PyPDF2. If loading an internet image into PIL, you MUST verify it succeeds and wrap the bytes: `Image.open(io.BytesIO(r.content))`.\n"
        "8. Set the pre-existing variable `output_filename` (type: str) to the desired filename.\n"
        "9. **KEEP IT CONCISE**: Do NOT hardcode massive lists of texts, questions, or raw data inside the python script or you will hit output token limits! ALWAYS use loops and generate small, representative dummy text if many items are needed.\n"
        "10. **GENERATING LONG CONTENT**: If the user DEMANDS a massive amount of real content (e.g. 'Generate a 40-question test with real questions'), do NOT hardcode it. Instead, you MUST use the `requests` library inside your `[PYTHON_EXEC]` block to call an external API or use an algorithm to generate it dynamically so your Python script stays short. For example, if you need text content, you can use `requests.post('https://integrate.api.nvidia.com/v1/chat/completions', headers={'Authorization': f'Bearer {os.environ.get(\"NVIDIA_API_KEY\", \"\")}'}, json={'model': 'meta/llama-3.3-70b-instruct', 'messages': [{'role': 'user', 'content': 'Generate 40 questions...'}], 'max_tokens': 2000})` to fetch the content programmatically (ensure you `import os` if doing this).\n"
        "11. **REPORTLAB FIXES**: When using `reportlab`, you MUST instantiate the document with the `output_buffer`, NOT a list or filename. Correct: `doc = SimpleDocTemplate(output_buffer)`. Incorrect: `doc = SimpleDocTemplate([])` or `doc = SimpleDocTemplate('file.pdf')`. You MUST NEVER call `.append()` on a `SimpleDocTemplate` object! Always build a list of flowables (e.g., `elements = []`, `elements.append(Paragraph(...))`) and pass it to `doc.build(elements)`.\n"
        "12. **NEWLINE FORMATTING**: CRITICAL: You MUST NEVER write your Python code on a single line! ALWAYS write properly formatted, multi-line Python with correct PEP-8 indentation. Do NOT squish code into a one-liner.\n\n"
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
