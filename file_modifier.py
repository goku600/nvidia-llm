"""
File modification engine.
- Asks the AI to generate Python code to modify the uploaded file
- Executes the code in a sandboxed environment with a timeout
- Returns the modified file bytes and filename
"""
import io
import sys
import json
import time
import traceback
import threading
import importlib
import logging

logger = logging.getLogger(__name__)

# Allowed modules inside sandboxed execution
SAFE_MODULES = {
    "io", "json", "csv", "re", "math", "datetime", "collections",
    "openpyxl", "pypdf", "docx", "PIL",
}

EXECUTION_TIMEOUT = 30  # seconds


def _build_modifier_prompt(doc_text: str, filename: str, user_request: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"
    return f"""You are a file modification assistant. The user has uploaded a file and wants you to modify it.

FILE NAME: {filename}
FILE TYPE: .{ext}
USER REQUEST: {user_request}

FILE CONTENT (extracted text):
{doc_text[:8000]}

Your task: Write a complete Python script that:
1. Reads the file from `input_bytes` (a `bytes` variable already available in scope)
2. Applies the requested modifications
3. Saves the result to `output_buffer` (an `io.BytesIO` variable already available in scope)
4. Sets `output_filename` (a string variable) to the output filename (e.g. "modified_{filename}")

Rules:
- Use only these libraries: io, json, csv, re, math, datetime, collections, openpyxl, pypdf, docx, PIL
- Do NOT use open(), os, sys, subprocess, requests, or any network/file system calls
- Read from `input_bytes` (bytes), write to `output_buffer` (BytesIO)
- For Excel: use openpyxl
- For Word: use python-docx (import docx)
- For CSV/TXT/JSON/MD/PY: use string manipulation and write encoded text to output_buffer
- Set output_filename to a descriptive name like "modified_report.xlsx"
- The script must be complete and runnable
- Only output the Python code, no explanations, no markdown fences

Example for Excel:
import openpyxl, io
wb = openpyxl.load_workbook(io.BytesIO(input_bytes))
ws = wb.active
# ... modifications ...
wb.save(output_buffer)
output_filename = "modified_{filename}"

Now write the Python script:"""


def _safe_exec(code: str, input_bytes: bytes) -> tuple[bytes | None, str | None, str | None]:
    """
    Execute AI-generated code in a restricted environment.
    Returns (output_bytes, output_filename, error_message)
    """
    output_buffer = io.BytesIO()
    output_filename = "modified_file"
    result = {"bytes": None, "filename": None, "error": None}

    # Restricted builtins — block dangerous functions
    safe_builtins = {
        k: v for k, v in __builtins__.items()
        if k not in ("open", "exec", "eval", "compile", "__import__",
                     "breakpoint", "input", "print")
    } if isinstance(__builtins__, dict) else {
        k: getattr(__builtins__, k)
        for k in dir(__builtins__)
        if k not in ("open", "exec", "eval", "compile", "__import__",
                     "breakpoint", "input", "print")
    }

    # Allow safe imports via a controlled __import__
    def safe_import(name, *args, **kwargs):
        base = name.split(".")[0]
        if base not in SAFE_MODULES:
            raise ImportError(f"Import of '{name}' is not allowed in sandbox.")
        return importlib.import_module(name, *args[1:], **kwargs)

    safe_builtins["__import__"] = safe_import
    safe_builtins["print"] = lambda *a, **k: None  # silence prints

    local_vars = {
        "input_bytes": input_bytes,
        "output_buffer": output_buffer,
        "output_filename": output_filename,
        "io": io,
    }

    global_vars = {"__builtins__": safe_builtins}

    def run():
        try:
            exec(code, global_vars, local_vars)
            result["bytes"] = local_vars["output_buffer"].getvalue()
            result["filename"] = local_vars.get("output_filename", "modified_file")
        except Exception as e:
            result["error"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(timeout=EXECUTION_TIMEOUT)

    if thread.is_alive():
        return None, None, f"Code execution timed out after {EXECUTION_TIMEOUT}s."

    if result["error"]:
        return None, None, result["error"]

    output_bytes = result["bytes"]
    if not output_bytes:
        return None, None, "Code ran but produced no output. Make sure you write to `output_buffer`."

    return output_bytes, result["filename"], None


def _build_create_prompt(user_request: str, ext: str) -> str:
    return f"""You are a file creation assistant. The user wants you to create a file from scratch.

USER REQUEST: {user_request}
OUTPUT FILE TYPE: .{ext}

Your task: Write a complete Python script that:
1. Creates the requested file content entirely in memory
2. Saves the result to `output_buffer` (an `io.BytesIO` variable already available in scope)
3. Sets `output_filename` (a string variable) to a descriptive filename with .{ext} extension

Rules:
- Use only these libraries: io, json, csv, re, math, datetime, collections, openpyxl, docx
- Do NOT use open(), os, sys, subprocess, requests, or any network/file system calls
- Write to `output_buffer` (BytesIO) only
- For .xlsx: use openpyxl
- For .docx: use python-docx (import docx)
- For .csv, .txt, .json, .md, .py, .html, .js, .yaml, .xml: encode as UTF-8 and write to output_buffer
- Set output_filename to a good descriptive name like "numbers_1_to_99999.txt"
- The script must be complete and runnable
- Only output the Python code, no explanations, no markdown fences

Example for a text file with numbers 1 to 10:
content = "\\n".join(str(i) for i in range(1, 11))
output_buffer.write(content.encode("utf-8"))
output_filename = "numbers_1_to_10.txt"

Now write the Python script:"""


def create_file(user_request: str, ext: str, model: str) -> tuple[bytes | None, str | None, str | None]:
    """
    Create a new file from scratch based on user request.
    Returns (file_bytes, filename, error_message)
    """
    import nvidia_client as ai

    prompt = _build_create_prompt(user_request, ext)
    messages = [{"role": "user", "content": prompt}]

    try:
        code_response = ai.chat(messages, model=model)
    except Exception as e:
        return None, None, f"AI failed to generate code: {e}"

    # Strip markdown fences if present
    code = code_response.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        code = "\n".join(lines[1:])
    if code.endswith("```"):
        code = code[:code.rfind("```")]
    code = code.strip()

    logger.info(f"Generated code for file creation:\n{code[:500]}")

    output_bytes, output_filename, error = _safe_exec(code, b"")

    if error:
        # Retry once with error feedback
        retry_prompt = (
            f"{prompt}\n\n"
            f"Your previous attempt failed with this error:\n{error}\n\n"
            "Fix the error and write the corrected Python script:"
        )
        messages = [{"role": "user", "content": retry_prompt}]
        try:
            code_response2 = ai.chat(messages, model=model)
            code2 = code_response2.strip()
            if code2.startswith("```"):
                code2 = "\n".join(code2.split("\n")[1:])
            if code2.endswith("```"):
                code2 = code2[:code2.rfind("```")]
            code2 = code2.strip()
            output_bytes, output_filename, error2 = _safe_exec(code2, b"")
            if error2:
                return None, None, f"Could not create the file after 2 attempts.\nLast error: {error2}"
        except Exception as e:
            return None, None, f"Retry failed: {e}"

    return output_bytes, output_filename, None


def modify_file(doc_text: str, file_bytes: bytes, filename: str,
                user_request: str, model: str) -> tuple[bytes | None, str | None, str | None]:
    """
    Main entry point.
    Returns (modified_bytes, output_filename, error_or_description)
    """
    import nvidia_client as ai

    prompt = _build_modifier_prompt(doc_text, filename, user_request)
    messages = [{"role": "user", "content": prompt}]

    try:
        code_response = ai.chat(messages, model=model)
    except Exception as e:
        return None, None, f"AI failed to generate code: {e}"

    # Strip markdown fences if present
    code = code_response.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        code = "\n".join(lines[1:])  # remove first fence line
    if code.endswith("```"):
        code = code[:code.rfind("```")]
    code = code.strip()

    logger.info(f"Generated code for file modification:\n{code[:500]}")

    # Execute the generated code
    output_bytes, output_filename, error = _safe_exec(code, file_bytes)

    if error:
        # Try once more with the error as feedback
        retry_prompt = (
            f"{prompt}\n\n"
            f"Your previous attempt failed with this error:\n{error}\n\n"
            "Fix the error and write the corrected Python script:"
        )
        messages = [{"role": "user", "content": retry_prompt}]
        try:
            code_response2 = ai.chat(messages, model=model)
            code2 = code_response2.strip()
            if code2.startswith("```"):
                lines = code2.split("\n")
                code2 = "\n".join(lines[1:])
            if code2.endswith("```"):
                code2 = code2[:code2.rfind("```")]
            code2 = code2.strip()
            output_bytes, output_filename, error2 = _safe_exec(code2, file_bytes)
            if error2:
                return None, None, f"Could not modify the file after 2 attempts.\nLast error: {error2}"
        except Exception as e:
            return None, None, f"Retry failed: {e}"

    return output_bytes, output_filename, None
