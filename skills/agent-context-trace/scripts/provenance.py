"""Operation inventory, scope expansion and local-file comparisons."""
import difflib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from records import Log, blocks, candidate_paths, has_type, text_content
from shell import analyze, path_of


def timestamp_seconds(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return (dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)).timestamp()


def operations(log, target=None):
    requests = {r["id"]: r for r in log.requests}
    with log.path.open("rb") as f:
        for ref, offsets in log.reply_offsets.items():
            if ref not in requests:
                continue
            if target:
                # Relative paths are possible, so use the filename as the prefilter.
                needle = Path(target).name
                raw_needles = (needle.encode(), json.dumps(needle)[1:-1].encode())
                hit = False
                for offset in offsets:
                    f.seek(offset)
                    line = f.readline()
                    if any(n in line for n in raw_needles):
                        hit = True
                        break
                if not hit:
                    continue
            message, last = log.reply(ref, f)
            req = requests[ref]
            for b in message["content"]:
                if b.get("type") != "tool_use":
                    continue
                if b["id"] in log.tool_errors:
                    continue
                name, inp = b["name"], b.get("input", {})
                location = log.tool_locations.get(b["id"], {})
                base = {"node_id": log.id, "session_id": log.session_id, "node_path": str(log.path),
                        "request": req["number"], "request_ref": ref, "tool_use_id": b["id"],
                        "timestamp": location.get("timestamp") or last.get("timestamp", req["timestamp"]), "offset": location.get("offset", offsets[-1]),
                        "tool": name, "input": inp}
                rows = []
                if name in ("Write", "Edit") and inp.get("file_path"):
                    rows = [{"path": path_of(inp["file_path"], log.cwd), "method": name, "evidence": "工具参数", "inputs": []}]
                elif name == "Bash":
                    rows = analyze(inp.get("command", ""), log.cwd)["writes"]
                for row in rows:
                    if not target or row["path"] == target:
                        yield dict(base, **row)


class Catalog:
    def __init__(self, projects_dir):
        self.projects_dir = Path(projects_dir).expanduser()
        self.logs = {}
        self._writes = {}

    def log(self, path):
        path = str(Path(path).expanduser().resolve())
        if path not in self.logs:
            self.logs[path] = Log(path)
        return self.logs[path]

    def find(self, target):
        target = str(Path(target).expanduser().resolve())
        modified = Path(target).stat().st_mtime if Path(target).exists() else None
        result = []
        for p in candidate_paths(self.projects_dir, Path(target).name):
            result.extend(op for op in operations(self.log(p), target)
                          if modified is None or timestamp_seconds(op["timestamp"]) <= modified)

        def priority(op):
            explicit = op["method"] != "命令生成" or op.get("confidence") == "explicit"
            return explicit, timestamp_seconds(op["timestamp"]), op["request"]

        return sorted(result, key=priority, reverse=True)

    def family(self, log):
        root = log.path.parent.parent if log.agent_id else log.path.with_suffix("")
        return [root.with_suffix(".jsonl")] + sorted((root / "subagents").glob("*.jsonl"))

    def parent(self, log):
        tid = log.meta.get("toolUseId")
        if not tid:
            return None
        needle = tid.encode()
        for p in self.family(log):
            if not p.exists() or p == log.path:
                continue
            with p.open("rb") as f:
                matched = any(needle in line and has_type(line, "assistant") for line in f)
            if not matched:
                continue
            parent = self.log(p)
            with parent.path.open("rb") as f:
                for req in parent.requests:
                    offsets = parent.reply_offsets.get(req["id"], [])
                    found = False
                    for offset in offsets:
                        f.seek(offset)
                        if needle in f.readline():
                            found = True
                            break
                    if not found:
                        continue
                    message, last = parent.reply(req["id"], f)
                    for b in message["content"]:
                        if b.get("type") == "tool_use" and b.get("id") == tid:
                            human = parent.latest_human(offsets[0]) if not parent.agent_id else None
                            return {"parent": parent, "request": req, "block": b,
                                    "timestamp": last.get("timestamp", req["timestamp"]),
                                    "human": parent.read(human["offset"], f) if human else None}
        return None

    def family_writes(self, log):
        if log.session_id not in self._writes:
            by_path = {}
            # Main-session writes also invalidate older subagent versions.
            # They do not turn a dispatch-only main node into a full trace.
            for p in self.family(log):
                if not p.exists():
                    continue
                other = self.log(p)
                for op in operations(other):
                    if op.get("confidence") == "ambiguous_argument":
                        continue
                    by_path.setdefault(op["path"], []).append(op)
            for ops in by_path.values():
                ops.sort(key=lambda o: (o["timestamp"], o["request"]))
            self._writes[log.session_id] = by_path
        return self._writes[log.session_id]


def strip_read_numbers(text):
    return re.sub(r"(?m)^\s*\d+(?:→|\t)", "", text)


def visible_text(text, method=""):
    match = re.search(r"Preview \(first ([^)]+)\):\s*\n", text)
    truncation = None
    if "<persisted-output>" in text and match:
        truncation = {"preview": match[1], "label": "截断，只看到前 " + match[1]}
        text = text[match.end():]
        text = re.sub(r"\n?(?:\.\.\.\s*)?</persisted-output>\s*$", "", text)
    text = re.sub(r"\n*<system-reminder>.*?</system-reminder>\s*", "", text, flags=re.S)
    if method == "Read":
        text = strip_read_numbers(text)
    return text, truncation


def comparison(path, text=None, full=False, image_hashes=None, shared=False, read_timestamp=None):
    p = Path(path)
    if not p.is_file():
        return {"status": "missing", "label": "文件已不在", "basis": "当前磁盘", "diff": None}
    if image_hashes:
        import hashlib
        match = hashlib.sha256(p.read_bytes()).hexdigest() in image_hashes
        if match:
            return {"status": "same", "label": "和现在一致", "basis": "图片字节哈希", "diff": None}
        if read_timestamp is None:
            return {"status": "unavailable", "label": "没法比", "basis": "图片哈希不同，缺少读取时间", "diff": None}
        changed = p.stat().st_mtime > timestamp_seconds(read_timestamp)
        return {"status": "different" if changed else "same", "label": "和现在不一致" if changed else "和现在一致", "basis": "图片缩放过，按修改时间判断", "diff": "文件修改时间晚于这次读取（读之后改过）" if changed else None}
    if text is None:
        return {"status": "unavailable", "label": "没法比", "basis": "没有可比较的原文", "diff": None}
    try:
        now = p.read_text(encoding="utf-8")
    except (UnicodeError, OSError):
        return {"status": "unavailable", "label": "没法比", "basis": "文件不可按 UTF-8 文本读取", "diff": None}
    if full and not shared:
        # Claude's textual tool renderer drops terminal newlines. Keep internal
        # whitespace exact, and document this single transport normalization.
        same = text.rstrip("\n") == now.rstrip("\n")
        basis = "全文逐字符比较（忽略工具传输丢失的末尾换行）"
    elif full and shared:
        same = now.rstrip("\n") in text
        basis = "多文件共同输出包含当前全文"
    else:
        # grep/sed/head can expose partial lines. Every visible nonempty line
        # must occur in the current file, in order; no similarity threshold.
        pos, same = 0, True
        for line in text.splitlines():
            if not line.strip():
                continue
            line = re.sub(r"^\d+[:-]", "", line)
            found = now.find(line, pos)
            if found < 0:
                same = False
                break
            pos = found + len(line)
        basis = "部分读取逐行核对（按出现顺序）"
    delta = None if same else "".join(difflib.unified_diff(text.splitlines(True), now.splitlines(True), fromfile="当时看到", tofile="现在磁盘"))
    return {"status": "same" if same else "different", "label": "和现在一致" if same else "和现在不一致", "basis": basis, "diff": delta}


def focus_paths(arguments):
    result = {}
    for arg in arguments:
        p = Path(arg).expanduser().resolve()
        children = sorted(x for x in p.rglob("*") if x.is_file() and x.name != ".DS_Store") if p.is_dir() else [p]
        for child in children:
            result.setdefault(str(child), []).append(str(p))
    return result
