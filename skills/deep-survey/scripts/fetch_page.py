#!/usr/bin/env python3
"""Collect public page evidence, including HTML, embedded JSON and linked resources.

Python standard library; no site credentials, database or Info2Action runtime dependency.
Request limits, redirect validation and article/main/body extraction are informed by
Info2Action src/fetch_url.py. Unlike its feed preview, evidence is not silently cut at 5k.
No JavaScript is evaluated by this parser. JS strings are labelled heuristic evidence.
See references/fetching.md. `ok` means extraction succeeded, NOT verified completeness.
"""
import argparse
import hashlib
import html
import ipaddress
import json
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

UA = "Mozilla/5.0 (compatible; ResearchEvidence/1.0)"
BLOCK = re.compile(r"just a moment|attention required|access denied|人机验证|安全验证|访问验证", re.I)
JS_STRING = re.compile(r'''(["'`])((?:\\.|(?!\1)[^\\])*)\1''', re.S)
LIBRARY = re.compile(r"(?:^|/)(?:polyfills[-.]|webpack[-.]|framework[-.]|main[-.]|_app[-.]|_buildManifest|_ssgManifest|vendor[-.])", re.I)
PRIVATE_ROUTE = re.compile(r"/(?:auth|login|logout|register|users?|orders?|payment|session|account)(?:/|\b)", re.I)


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(url):
    p = urllib.parse.urlsplit(url)
    if p.scheme not in ("https", "http") or not p.hostname or p.username or p.password:
        raise ValueError("Only public HTTP(S) URLs without credentials are accepted")
    return urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or "/", p.query, ""))


# Clash / Surge fake-ip: with the proxy owning DNS, every public domain resolves into 198.18.0.0/15.
# Accept that range only for domain names; a literal 198.18.x.x URL is still rejected.
FAKE_IP = ipaddress.ip_network("198.18.0.0/15")


def public_url(url):
    url = canonical(url)
    host = urllib.parse.urlsplit(url).hostname
    if host.lower().rstrip(".") in ("localhost", "localhost.localdomain"):
        raise ValueError("Private host is not a public source")
    try:
        addresses, literal = [str(ipaddress.ip_address(host))], True
    except ValueError:
        try:  # inet_aton also accepts integer, short, hex and octal IPv4 forms (3323068417, 198.18.1, 0xc6.0x12.0.1)
            addresses, literal = [socket.inet_ntoa(socket.inet_aton(host))], True
        except OSError:
            addresses, literal = list({x[4][0] for x in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)}), False

    def allowed(a):
        ip = ipaddress.ip_address(a)
        return ip.is_global or (not literal and ip in FAKE_IP)

    if not all(allowed(a) for a in addresses):
        raise ValueError("Private or reserved network targets are not public sources")
    return url


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class RequestCounter(urllib.request.BaseHandler):
    """Count transport attempts, including redirects, under one shared limit."""
    def __init__(self, records, limit):
        self.records = records; self.limit = limit

    def http_request(self, req):
        if len(self.records) >= self.limit: raise ValueError("request_budget")
        self.records.append({"url": req.full_url, "method": req.get_method(), "attempted_at": now()})
        return req

    https_request = http_request


def decode_js(s):
    # Decode literal escapes without eval or unicode_escape corrupting Chinese text.
    s = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m[1], 16)), s)
    s = re.sub(r"\\x([0-9a-fA-F]{2})", lambda m: chr(int(m[1], 16)), s)
    s = re.sub(r"\\([nrt\\/'\"`])", lambda m: {"n": "\n", "r": "\r", "t": "\t"}.get(m[1], m[1]), s)
    return s.encode("utf-16", "surrogatepass").decode("utf-16", errors="replace")


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = []; self.meta = {}; self.parts = {"article": [], "main": [], "body": []}
        self.depth = {"article": 0, "main": 0, "body": 0, "title": 0}
        self.skip = 0; self.script = None; self.scripts = []; self.resources = []; self.links = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.depth: self.depth[tag] += 1
        if tag == "meta": self.meta[(a.get("property") or a.get("name") or "").lower()] = a.get("content", "")
        if tag == "a" and a.get("href"): self.links.append(a["href"])
        if tag == "script":
            self.script = {"attrs": a, "chunks": []}
            if a.get("src"): self.resources.append(a["src"])
        if tag in ("style", "svg", "nav", "noscript"): self.skip += 1
        if tag in ("p", "div", "section", "li", "tr", "br", "h1", "h2", "h3", "h4"):
            for parts in self.parts.values(): parts.append("\n")

    def handle_endtag(self, tag):
        if tag == "script" and self.script is not None:
            self.scripts.append(self.script); self.script = None
        if tag in self.depth: self.depth[tag] = max(0, self.depth[tag] - 1)
        if tag in ("style", "svg", "nav", "noscript"): self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if self.script is not None:
            self.script["chunks"].append(data); return
        if self.depth["title"]: self.title.append(data)
        if not self.skip:
            for tag in self.parts:
                if self.depth[tag]: self.parts[tag].append(data)

    def text(self):
        for tag in ("article", "main", "body"):
            text = re.sub(r"[ \t\r]+", " ", " ".join(self.parts[tag]))
            text = re.sub(r"\n\s*\n+", "\n", text).strip()
            if text: return text
        return ""


def flatten_json(value, path="$", limit=10000):
    lines = []
    def walk(v, key):
        if len(lines) >= limit: return
        if isinstance(v, dict):
            for k, item in v.items():
                if re.search(r"(?:password|secret|access_token|refresh_token|cookie|authorization)", k, re.I): continue
                walk(item, f"{key}.{k}")
        elif isinstance(v, list):
            for i, item in enumerate(v): walk(item, f"{key}[{i}]")
        elif v is not None: lines.append(f"{key}: {v}")
    walk(value, path)
    return "\n".join(lines), len(lines) >= limit


def script_evidence(body):
    values = []
    for m in JS_STRING.finditer(body):
        value = decode_js(m[2]).strip()
        # Preserve prose, numbers with context and data values, not a dump of minified code.
        if len(value) < 8 or len(value) > 25000 or value.startswith(("data:", "http://", "https://", "./", "/assets/")): continue
        if "${" in value or not (re.search(r"[\u3400-\u9fff]", value) or len(value.split()) >= 4): continue
        context = body[max(0, m.start()-80):m.start()]
        key = re.search(r"([\w$]+)\s*:\s*$", context)
        values.append((key[1] + ": " if key else "") + value)
    return "\n".join(dict.fromkeys(values))


def resource_links(body, base):
    links = []
    # Literal ES imports and .js dependencies. Only observed paths, never guessed hashes.
    for m in JS_STRING.finditer(body):
        v = decode_js(m[2])
        if re.fullmatch(r"(?:\./|\.\./|/)[^\s{}]+\.js(?:\?[^\s]*)?", v):
            links.append((urllib.parse.urljoin(base, v), "script"))
    # Common declarative API maps: {url: BASE + 'path', type: 'get'}.
    constants = {m[1]: decode_js(m[3]) for m in re.finditer(r'''\b([A-Za-z_$][\w$]*)\s*=\s*(["'])([^"']*)\2''', body)}
    pattern = r'''\burl\s*:\s*(?:([A-Za-z_$][\w$]*)\s*\+\s*)?(["'])([^"']+)\2\s*,\s*(?:type|method)\s*:\s*(["'])get\4'''
    for m in re.finditer(pattern, body, re.I):
        if m[1] and m[1] not in constants: continue
        path = constants.get(m[1], "") + decode_js(m[3])
        if "{" not in path and "${" not in path and not PRIVATE_ROUTE.search(path):
            links.append((urllib.parse.urljoin(base, path), "json"))
    return links


class Collector:
    def __init__(self, out_dir, max_requests=12, timeout=15, max_bytes=8*1024*1024, replay=None):
        self.out = Path(out_dir); self.out.mkdir(parents=True, exist_ok=True)
        self.limit = max_requests; self.timeout = timeout; self.max_bytes = max_bytes
        self.cache = {}; self.requests = []; self.http_requests = []; self.snapshots = []; self.replay = None
        if replay:
            replay = Path(replay); self.replay = {}
            for item in json.loads(replay.read_text()):
                path = Path(item["path"])
                self.replay[canonical(item["url"])] = (path if path.is_absolute() else replay.parent/path, item)

    def get(self, url):
        url = canonical(url)
        if url in self.cache: return self.cache[url]
        if max(len(self.requests), len(self.http_requests)) >= self.limit: return {"url": url, "error": "request_budget", "body": ""}
        begin = time.monotonic(); rec = {"url": url, "retrieved_at": now(), "network": self.replay is None}
        try:
            if self.replay is not None:
                if url not in self.replay: raise FileNotFoundError("Not present in the fixed evidence index")
                path, item = self.replay[url]; data = path.read_bytes()
                expected = item.get("sha256")
                if expected and hashlib.sha256(data).hexdigest() != expected: raise ValueError("Snapshot hash mismatch")
                final = url; code = 200; ct = item.get("content_type") or {".js": "application/javascript", ".json": "application/json", ".pdf": "application/pdf"}.get(path.suffix, "text/html")
                rec["captured_at"] = item.get("captured_at") or item.get("retrieved_at"); rec["replay"] = True
            else:
                public_url(url)
                req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.8,en;q=0.7"})
                opener = urllib.request.build_opener(SafeRedirect(), RequestCounter(self.http_requests, self.limit))
                try: response = opener.open(req, timeout=self.timeout)
                except urllib.error.HTTPError as e: response = e
                with response as r:
                    final = canonical(r.geturl()); code = r.code; ct = r.headers.get("Content-Type", "")
                    data = r.read(self.max_bytes + 1)
            if len(data) > self.max_bytes: raise ValueError("Response exceeded byte limit")
            enc = re.search(r"charset=([^;\s]+)", ct, re.I)
            body = data.decode(enc[1].strip('"') if enc else "utf-8", errors="replace")
            sha = hashlib.sha256(data).hexdigest(); suffix = ".json" if "json" in ct else ".js" if "javascript" in ct or urllib.parse.urlsplit(final).path.endswith('.js') else ".pdf" if "pdf" in ct else ".html"
            path = self.out/(sha[:20]+suffix); path.write_bytes(data)
            rec.update(final_url=final, http_status=code, bytes=len(data), sha256=sha, path=str(path.resolve()), content_type=ct)
            result = {**rec, "body": body}
            if code >= 400: result["error"] = f"http_{code}"
            self.snapshots.append({k: v for k, v in rec.items() if k != "network"})
        except Exception as e:
            rec["error"] = "request_budget" if str(e) == "request_budget" else type(e).__name__ + ": " + str(e)[:250]
            result = {**rec, "body": "", "error": rec["error"]}
        rec["elapsed_ms"] = round((time.monotonic()-begin)*1000)
        self.requests.append(rec); self.cache[url] = result
        return result

    def collect(self, url, resources="auto"):
        start = len(self.requests); http_start = len(self.http_requests); root = canonical(url); origin = urllib.parse.urlsplit(root).netloc
        queue = [(root, "page")]; visited = set(); sections = []; missing = []; decisions = []; title = ""; links = []; dynamic = False; blocked = False
        while queue:
            target, kind = queue.pop(0); target = canonical(target)
            if target in visited: continue
            visited.add(target)
            if urllib.parse.urlsplit(target).netloc != origin: continue
            if kind == "script" and (LIBRARY.search(urllib.parse.urlsplit(target).path) or PRIVATE_ROUTE.search(urllib.parse.urlsplit(target).path)): continue
            item = self.get(target)
            if item.get("error"):
                missing.append({"url": target, "reason": item["error"]}); continue
            body = item["body"]; ct = item.get("content_type", ""); additions = []; rich_embedded = False; substantial_article = False
            if "pdf" in ct or body.startswith("%PDF-") or ct.startswith(("image/", "audio/", "video/")):
                missing.append({"url": target, "reason": "unsupported_format", "content_type": ct}); continue
            if kind == "json" or "json" in ct:
                try:
                    text, limited = flatten_json(json.loads(body))
                    sections.append({"url": target, "method": "json", "text": text, "truncated": limited})
                except json.JSONDecodeError: missing.append({"url": target, "reason": "Invalid JSON"})
            elif kind == "script" or "javascript" in ct:
                text = script_evidence(body)
                if text: sections.append({"url": target, "method": "js_literal_heuristic", "text": text, "caution": "Extracted literal strings; context must be verified in the raw snapshot."})
                additions = resource_links(body, target)
            else:
                parser = PageParser(); parser.feed(body); text = parser.text()
                substantial_article = len("".join(parser.parts["article"]).strip()) >= 5000
                if target == root:
                    title = parser.meta.get("og:title") or "".join(parser.title).strip()
                    links = list(dict.fromkeys(urllib.parse.urljoin(target, x) for x in parser.links if not x.startswith(("javascript:", "mailto:", "tel:"))))
                if BLOCK.search((title + " " + text)[:2500]) and len(text) < 2000:
                    blocked = True; missing.append({"url": target, "reason": "Challenge or blocked page"}); continue
                if text: sections.append({"url": target, "method": "html", "text": text})
                for script in parser.scripts:
                    raw = "".join(script["chunks"]).strip(); attrs = script["attrs"]
                    if not raw: continue
                    if "json" in attrs.get("type", "") or attrs.get("id") == "__NEXT_DATA__":
                        try:
                            structured, limited = flatten_json(json.loads(raw))
                            sections.append({"url": target, "method": "embedded_json", "text": structured, "truncated": limited})
                            rich_embedded = rich_embedded or (len(structured) >= 2000 and not limited)
                        except json.JSONDecodeError: missing.append({"url": target, "reason": "Embedded JSON could not be parsed"})
                    elif raw.startswith(("window.", "self.")) and not (resources == "auto" and substantial_article):
                        literals = script_evidence(raw)
                        if literals: sections.append({"url": target, "method": "inline_js_heuristic", "text": literals})
                dynamic = dynamic or bool(parser.resources)
                # Prefer route entries, then other observed application chunks; never crawl site links.
                additions = [(urllib.parse.urljoin(target, x), "script") for x in parser.resources]
                additions.sort(key=lambda x: ("/pages/" not in x[0], x[0]))
                if additions:
                    reason = "resources_disabled" if not resources else "substantial_article" if resources == "auto" and substantial_article else "rich_embedded_json" if resources == "auto" and rich_embedded else "follow_observed_resources"
                    decisions.append({"url": target, "reason": reason, "observed_script_tags": len(additions)})
            if resources and not (resources == "auto" and (rich_embedded or substantial_article)):
                for link, linked_kind in additions:
                    try: clean = canonical(link)
                    except ValueError: continue
                    if urllib.parse.urlsplit(clean).netloc == origin and clean not in visited and (clean, linked_kind) not in queue:
                        queue.append((clean, linked_kind))
        combined = "\n\n".join(f"## {x['url']} [{x['method']}]\n{x['text']}" for x in sections)
        if blocked: status = "blocked"
        elif not sections and any(x['reason'] == 'unsupported_format' for x in missing): status = "unsupported"
        elif not sections:
            status = "partial" if missing and (self.replay is not None or any(x['reason'] == 'request_budget' for x in missing)) else "network_error" if missing and not dynamic else "needs_browser" if dynamic else "empty"
        elif missing or any(x.get("truncated") for x in sections): status = "partial"
        else: status = "ok"
        return {"url": root, "title": title, "status": status, "coverage": "not_assessed", "retrieved_at": now(), "text": combined,
                "sections": sections, "links": links, "missing_resources": missing, "resource_decisions": decisions,
                "requests": self.requests[start:], "http_requests": self.http_requests[http_start:],
                "network_attempts": sum(x['network'] for x in self.requests[start:]), "actual_network_requests": len(self.http_requests)-http_start,
                "evidence_reads": len(self.requests)-start, "snapshots": [x for x in self.snapshots if x['url'] in visited]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("urls", nargs="+"); ap.add_argument("--out", type=Path)
    ap.add_argument("--out-dir", type=Path, required=True); ap.add_argument("--replay", type=Path)
    ap.add_argument("--max-requests", type=int, default=12); ap.add_argument("--timeout", type=float, default=15)
    ap.add_argument("--max-bytes", type=int, default=8*1024*1024)
    mode = ap.add_mutually_exclusive_group(); mode.add_argument("--no-resources", action="store_true"); mode.add_argument("--all-resources", action="store_true")
    args = ap.parse_args()
    if min(args.max_requests, args.timeout, args.max_bytes) <= 0: ap.error("limits must be positive")
    collector = Collector(args.out_dir, args.max_requests, args.timeout, args.max_bytes, args.replay)
    resource_mode = False if args.no_resources else "all" if args.all_resources else "auto"
    try: results = [collector.collect(url, resource_mode) for url in args.urls]
    except ValueError as e: ap.error(str(e))
    result = {"schema_version": 1, "pages": results, "actual_network_requests": len(collector.http_requests),
              "network_attempts": sum(x['network'] for x in collector.requests), "http_requests": collector.http_requests,
              "evidence_reads": len(collector.requests), "snapshots": collector.snapshots}
    (args.out_dir/'index.json').write_text(json.dumps(collector.snapshots, ensure_ascii=False, indent=2)+'\n')
    output = json.dumps(result, ensure_ascii=False, indent=2)+'\n'
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True); args.out.write_text(output)
        print(json.dumps({"output": str(args.out), "pages": [{"url": x['url'], "status": x['status'], "chars": len(x['text']), "missing_resources": len(x['missing_resources'])} for x in results], "actual_network_requests": result['actual_network_requests'], "evidence_reads": result['evidence_reads']}, ensure_ascii=False))
    else: print(output, end="")
    return 0 if all(x['status'] == 'ok' for x in results) else 4


if __name__ == '__main__':
    raise SystemExit(main())
