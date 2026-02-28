import io

SAFE_MODULES = {"reportlab"}

def _safe_exec(code: str):
    output_buffer = io.BytesIO()

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

    _real_import = __import__
    def safe_import(name, globals=None, locals=None, fromlist=(), level=0):
        base = name.split(".")[0]
        if base not in SAFE_MODULES:
            raise ImportError(f"Import of '{name}' is not allowed in sandbox.")
        return _real_import(name, globals, locals, fromlist, level)

    safe_builtins["__import__"] = safe_import

    local_vars = {
        "output_buffer": output_buffer,
        "io": io,
    }

    global_vars = {"__builtins__": safe_builtins}

    try:
        exec(code, global_vars, local_vars)
        print("SUCCESS")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")

code = """
from reportlab.pdfgen import canvas
c = canvas.Canvas(output_buffer)
c.drawString(100, 750, 'Hello World')
c.save()
"""

_safe_exec(code)
