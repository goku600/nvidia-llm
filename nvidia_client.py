import requests
import json
import base64
from config import (
    NVIDIA_API_KEY, NVIDIA_API_URL,
    MAX_TOKENS, TEMPERATURE, TOP_P, TOP_K,
    CHAT_MODEL, VISION_MODEL, CODE_MODEL, DOC_MODEL
)


def _build_headers():
    return {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Accept": "application/json",
    }


def _post(payload: dict) -> str:
    """Send a request to NVIDIA API and return the assistant reply text."""
    headers = _build_headers()
    response = requests.post(NVIDIA_API_URL, headers=headers, json=payload, timeout=120)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


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
        "stream": False,
    }
    if thinking:
        payload["chat_template_kwargs"] = {"enable_thinking": True}
    return payload


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

def chat(history: list[dict]) -> str:
    """
    history: list of {"role": "user"|"assistant", "content": str}
    Returns the assistant reply.
    """
    payload = _base_payload(CHAT_MODEL, history, thinking=True)
    return _post(payload)


# ---------------------------------------------------------------------------
# Code Assistant
# ---------------------------------------------------------------------------

def code_assist(history: list[dict]) -> str:
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
    payload = _base_payload(CODE_MODEL, messages, thinking=True)
    return _post(payload)


# ---------------------------------------------------------------------------
# Document Q&A
# ---------------------------------------------------------------------------

def document_qa(document_text: str, history: list[dict]) -> str:
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
    payload = _base_payload(DOC_MODEL, messages)
    return _post(payload)


# ---------------------------------------------------------------------------
# Image Analysis
# ---------------------------------------------------------------------------

def image_analysis(image_b64: str, mime_type: str, user_prompt: str, history: list[dict]) -> str:
    """
    image_b64: base64-encoded image string
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

    # Build current message with image + text
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
                "text": user_prompt if user_prompt else "Describe this image in detail.",
            },
        ],
    }

    # For vision, we send system + past text history + current image message
    text_history = []
    for msg in history:
        if isinstance(msg.get("content"), str):
            text_history.append(msg)

    messages = [system] + text_history + [current_message]
    payload = _base_payload(VISION_MODEL, messages)
    return _post(payload)
