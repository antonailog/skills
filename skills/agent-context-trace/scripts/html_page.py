"""Package the trace contract and trusted viewer assets into one offline page."""
import base64
import hashlib
import json
import re
from pathlib import Path


def render_html(data):
    assets = Path(__file__).resolve().parent.parent / "assets"
    template = (assets / "viewer.html").read_text(encoding="utf-8")
    # One trusted script block, one exact hash; no CDN or runtime loader.
    script = "\n;\n".join((assets / name).read_text(encoding="utf-8") for name in (
        "vendor/markdown-it.min.js", "vendor/overlayscrollbars.browser.es6.min.js", "viewer.js"))
    style = "\n".join((assets / name).read_text(encoding="utf-8") for name in (
        "vendor/overlayscrollbars.min.css", "viewer.css"))
    # JSON is an inert script data block. Escape HTML delimiters even inside
    # recorded commands; never allow a source string to terminate that block.
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    for char, escaped in (("&", "\\u0026"), ("<", "\\u003c"), (">", "\\u003e"),
                          ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        payload = payload.replace(char, escaped)
    script_hash = base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode("ascii")
    parts = {"STYLE": style, "SCRIPT": script, "DATA": payload, "SCRIPT_HASH": script_hash}
    # Substitute in a single pass: source text can itself contain a marker.
    return re.sub(r"\{\{(STYLE|SCRIPT|DATA|SCRIPT_HASH)\}\}", lambda m: parts[m[1]], template)
