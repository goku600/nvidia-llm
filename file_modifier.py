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

# Strictly forbidden modules inside sandboxed execution
FORBIDDEN_MODULES = {
    "os", "sys", "subprocess", "shutil", "pty", "ptyprocess", "multiprocessing", "threading", "_thread"
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
4. Sets `output_filename` (a string variable) to the output filename (e.g. "modified_{filename}"). Optional if just printing data.

Rules:
- You can import any standard python library or common data science pip package (pandas, numpy, reportlab, docx, openpyxl, bs4, etc) except for OS/subprocess modules.
- Do NOT use os, sys, subprocess, or any local file system calls. (You can use open() to read the input or save the output).
- You MAY use `requests` or `urllib` to download files/images. ALWAYS use a User-Agent and check for HTTP errors (e.g. `r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}); r.raise_for_status()`).
- Google Sheets: You ALREADY have a pre-authenticated `gspread_client` variable in scope. DO NOT use oauth2client, do NOT look for a client_secret.json, and do NOT attempt to authenticate. Just do: `import gspread; sheet = gspread_client.open("Sheet Name").sheet1`. DO NOT explicitly `import gspread_client` because it's already defined dynamically. Use `sheet.append_row()` to add new data to the bottom. Use `sheet.update_cell(row, col, value)` or `sheet.update([range], [[values]])` ONLY if the user explicitly asks to modify/overwrite existing data. Use `sheet.delete_rows(row_index)` if asked to remove data. If reading data to show the user, pull records with `sheet.get_all_records()`, use `pandas.DataFrame(data)`, and save to `output_buffer` as a CSV.
- Read from `input_bytes` (bytes) or `open('input.txt', 'r')`, write to `output_buffer` (BytesIO) or `open('output_filename.ext', 'wb')`.
- For Excel: use openpyxl (import openpyxl). Save directly to the buffer: `wb.save(output_buffer)`
- For Word: use python-docx (import docx). Save directly to the buffer: `doc.save(output_buffer)`. DO NOT save to a string filename. To convert PDF to Word, extract text using pypdf (e.g., `reader = pypdf.PdfReader(io.BytesIO(input_bytes)); text = reader.pages[0].extract_text()`), create a new `docx.Document()`, add text as paragraphs, and save it to `output_buffer`. Adding hyperlinks in docx requires XML manipulation (there is no `run.hyperlink`). To add a hyperlink, you MUST import `from docx.oxml.shared import OxmlElement, qn` and build the hyperlink element manually, OR simply output the URL as plain text.
- For PDF creation/conversion: use reportlab. You MUST explicitly import needed classes like `from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer` or `from reportlab.pdfgen import canvas`. DO NOT import 'Link' from reportlab.platypus. DO NOT try to fix execution errors by assigning to `result["bytes"]`. Just write to or assign to `output_buffer`.
- For Images: use PIL (Pillow). Save directly to the buffer: `image.save(output_buffer, format='PNG')`. If loading an image from the web, wrap it in BytesIO: `Image.open(io.BytesIO(r.content))`.
- For CSV/TXT/JSON/MD/PY: use string manipulation and write encoded text to output_buffer
- If the user asks a question (e.g. "how many words", "extract the text", "what is the sum"), simply use `print()` to output the result! The system will capture your printed output and show it to you so you can answer the user directly. DO NOT save a file if just answering a question!
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

    # Restricted builtins — block dangerous functions while allowing classes/types
    dangerous_builtins = {
        "open", "exec", "eval", "compile", "breakpoint", "input"
    }
    
    # We must allow `__import__` (which we override) and standard core types/exceptions
    # otherwise deep libraries like requests and google-auth fail on instantiation.
    safe_builtins = {
        k: v for k, v in __builtins__.items()
        if k not in dangerous_builtins
    } if isinstance(__builtins__, dict) else {
        k: getattr(__builtins__, k)
        for k in dir(__builtins__)
        if k not in dangerous_builtins
    }

    _real_import = __import__

    # Allow safe imports via a controlled __import__
    def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        base = name.split(".")[0]
        if base in FORBIDDEN_MODULES:
            raise ImportError(f"Import of forbidden module '{name}' is blocked for security.")
        
        # Verify the module actually exists before attempting to import to fail fast
        try:
            import importlib.util
            if importlib.util.find_spec(base) is None:
                raise ImportError(f"Module '{base}' is not installed in the environment.")
        except Exception:
            pass # Fallback to real import if find_spec fails
            
        try:
            return _real_import(name, globals, locals, fromlist, level)
        except ImportError as e:
            # Let it bubble up, but log it so we know which dependency failed.
            raise ImportError(f"Sandbox attempted to load '{name}' but failed: {e}")

    safe_builtins["__import__"] = safe_import

    console_output = io.StringIO()
    def safe_print(*args, **kwargs):
        kwargs['file'] = console_output
        print(*args, **kwargs)
        
    safe_builtins["print"] = safe_print

    local_vars = {
        "input_bytes": input_bytes,
        "output_buffer": output_buffer,
        "output_filename": output_filename,
        "io": io,
    }
    
    # Securely inject Google Sheets authenticated client if available
    gspread_client = None
    try:
        import os
        import gspread
        creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
        if creds_json:
            creds_dict = json.loads(creds_json)
            gspread_client = gspread.service_account_from_dict(creds_dict)
    except Exception as e:
        logger.warning(f"Failed to initialize gspread client: {e}")
    if gspread_client:
        local_vars["gspread_client"] = gspread_client
        local_vars["gspread"] = __import__("gspread")

    class SandboxedFile:
        def __init__(self, name, mode):
            import os
            self.name = os.path.basename(str(name))
            self.mode = mode
            if 'r' in mode:
                if 'b' in mode:
                    self.buf = io.BytesIO(input_bytes)
                else:
                    try:
                        text = input_bytes.decode('utf-8')
                    except UnicodeDecodeError:
                        text = input_bytes.decode('latin-1')
                    self.buf = io.StringIO(text)
            else:
                if 'b' in mode:
                    self.buf = io.BytesIO()
                else:
                    self.buf = io.StringIO()

        def write(self, data): return self.buf.write(data)
        def read(self, *args, **kwargs): return self.buf.read(*args, **kwargs)
        def readlines(self): return self.buf.readlines()
        def __iter__(self): return self.buf.__iter__()
        def __enter__(self): return self
        def __exit__(self, exc_type, exc_val, exc_tb): self.close()
        def close(self):
            if 'w' in self.mode or 'a' in self.mode:
                val = self.buf.getvalue()
                if isinstance(val, str):
                    val = val.encode('utf-8')
                local_vars["output_buffer"].write(val)
                local_vars["output_filename"] = self.name

    def safe_open(file, mode='r', *args, **kwargs):
        return SandboxedFile(file, mode)

    safe_builtins["open"] = safe_open

    global_vars = {"__builtins__": safe_builtins}

    def run():
        try:
            exec(code, global_vars, local_vars)
            out_buf = local_vars.get("output_buffer")
            if isinstance(out_buf, bytes):
                result["bytes"] = out_buf
            elif hasattr(out_buf, "getvalue"):
                result["bytes"] = out_buf.getvalue()
            else:
                result["bytes"] = str(out_buf).encode("utf-8")
            result["filename"] = local_vars.get("output_filename", "modified_file")
        except Exception as e:
            result["error"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(timeout=EXECUTION_TIMEOUT)

    if thread.is_alive():
        return None, None, f"Code execution timed out after {EXECUTION_TIMEOUT}s.", None

    if result["error"]:
        return None, None, result["error"], None

    output_bytes = result["bytes"]
    if not output_bytes:
        # Instead of throwing an error, we treat empty output_bytes as a successful "silent" execution
        # (e.g. updating a remote database without saving a local file).
        return None, None, None, console_output.getvalue()

    return output_bytes, result["filename"], None, console_output.getvalue()


def execute_python_code(code: str, input_bytes: bytes = b"") -> tuple[bytes | None, str | None, str | None, str | None]:
    """
    Execute python code generated by the LLM in the sandbox.
    Returns (output_bytes, output_filename, error_message, printed_text)
    """
    # Simply delegate to the sandbox
    return _safe_exec(code, input_bytes)
