import requests
import json
import base64
from config import (
    NVIDIA_API_KEY, NVIDIA_API_URL,
    MAX_TOKENS, TEMPERATURE, TOP_P, TOP_K,
    CHAT_MODEL, VISION_MODEL, CODE_MODEL, DOC_MODEL
)

NVIDIA_ASSET_URL = "https://integrate.api.nvidia.com/v1/files"


def _build_headers(stream: bool = False):
    return {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Accept": "text/event-stream" if stream else "application/json",
    }


def _post(payload: dict) -> str:
    """Send a streaming request to NVIDIA API and return the full assembled reply."""
    payload = {**payload, "stream": True}
    headers = _build_headers(stream=True)
    response = requests.post(
        NVIDIA_API_URL, headers=headers, json=payload,
        stream=True, timeout=(10, 300)  # 10s connect, 300s read
    )
    response.raise_for_status()

    full_text = []
    for line in response.iter_lines():
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
                    full_text.append(content)
            except (json.JSONDecodeError, KeyError, IndexError):
                continue

    return "".join(full_text)


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
        "stream": False,  # overridden in _post
    }
    if thinking:
        payload["chat_template_kwargs"] = {"enable_thinking": True}
    return payload


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

def chat(history: list[dict], model: str = CHAT_MODEL) -> str:
    """
    history: list of {"role": "user"|"assistant", "content": str}
    Returns the assistant reply.
    """
    payload = _base_payload(model, history)
    return _post(payload)


# ---------------------------------------------------------------------------
# Code Assistant
# ---------------------------------------------------------------------------

def code_assist(history: list[dict], model: str = CODE_MODEL) -> str:
    system = {
        "role": "system",
        "content": (
            "You are an expert software engineer and code assistant. "
            "Help the user write, debug, review, and explain code. "
            "Always provide clear explanations alongside any code you write. "
            "Format code blocks with the appropriate language tag."
        ),
    }
    messages = [system] + history
    payload = _base_payload(model, messages)
    return _post(payload)


# ---------------------------------------------------------------------------
# Document Q&A
# ---------------------------------------------------------------------------

def document_qa(document_text: str, history: list[dict], model: str = DOC_MODEL) -> str:
    system = {
        "role": "system",
        "content": (
            "You are a helpful document analysis assistant. "
            "The user has provided a document. Answer their questions "
            "accurately based on the document content. "
            "If the answer is not in the document, say so clearly.\n\n"
            f"--- DOCUMENT START ---\n{document_text}\n--- DOCUMENT END ---"
        ),
    }
    messages = [system] + history
    payload = _base_payload(model, messages)
    return _post(payload)


# ---------------------------------------------------------------------------
# Image Analysis
# ---------------------------------------------------------------------------

def _upload_image_asset(image_bytes: bytes, mime_type: str) -> str:
    """
    Upload image to NVIDIA asset API and return the asset ID (nvcf-asset-id).
    NVIDIA vision models require images to be uploaded as assets first.
    """
    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": mime_type,
        "NVCF-ASSET-DESCRIPTION": "telegram-bot-image",
    }
    response = requests.post(
        NVIDIA_ASSET_URL,
        headers=headers,
        data=image_bytes,
        timeout=(10, 60),
    )
    response.raise_for_status()
    result = response.json()
    # Returns {"assetId": "...", ...}
    asset_id = result.get("assetId") or result.get("asset_id") or result["id"]
    return asset_id


def image_analysis(image_bytes: bytes, mime_type: str, user_prompt: str, history: list[dict]) -> str:
    """
    image_bytes: raw image bytes
    mime_type: e.g. "image/jpeg", "image/png"
    user_prompt: the user's question about the image
    history: previous turns (without the current image message)
    """
    system = {
        "role": "system",
        "content": (
            "You are a powerful vision AI assistant. "
            "Analyze images thoroughly and answer questions about them in detail."
        ),
    }

    prompt = user_prompt if user_prompt else "Describe this image in detail."

    # Try asset upload first (preferred by NVIDIA), fall back to base64 inline
    try:
        asset_id = _upload_image_asset(image_bytes, mime_type)
        current_message = {
            "role": "user",
            "content": f'<img src="data:image/jpeg;asset_id,{asset_id}" />\n{prompt}',
        }
        # asset IDs require a special header
        extra_headers = {"NVCF-INPUT-ASSET-REFERENCES": asset_id}
    except Exception:
        # Fallback: send as base64 inline (works for smaller images)
        image_b64 = base64.b64encode(image_bytes).decode()
        current_message = {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{image_b64}"
                    },
                },
                {
                    "type": "text",
                    "text": prompt,
                },
            ],
        }
        extra_headers = {}

    # For vision, we send system + past text history + current image message
    text_history = [msg for msg in history if isinstance(msg.get("content"), str)]
    messages = [system] + text_history + [current_message]

    payload = _base_payload(VISION_MODEL, messages)
    payload = {**payload, "stream": True}

    headers = {**_build_headers(stream=True), **extra_headers}
    response = requests.post(
        NVIDIA_API_URL, headers=headers, json=payload,
        stream=True, timeout=(10, 300)
    )
    response.raise_for_status()

    full_text = []
    for line in response.iter_lines():
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
                    full_text.append(content)
            except (json.JSONDecodeError, KeyError, IndexError):
                continue

    return "".join(full_text)
