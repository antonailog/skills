"""Read-only JSONL indexing and exact wire-message reconstruction (stdlib only)."""
import copy
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


BJT = timezone(timedelta(hours=8))


def packed(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(packed(value).encode("utf-8")).hexdigest()


def has_type(line, kind):
    key = kind.encode()
    return b'"type":"' + key + b'"' in line or b'"type": "' + key + b'"' in line


def local_time(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(BJT).isoformat()


def text_content(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(text_content(b.get("content", b.get("text", ""))) for b in content if isinstance(b, dict))
    return ""


def blocks(content):
    return content if isinstance(content, list) else [{"type": "text", "text": content}]


def human_message(entry):
    if entry.get("type") != "user" or entry.get("isMeta") or entry.get("isCompactSummary"):
        return False
    content = entry.get("message", {}).get("content", "")
    if any(b.get("type") == "tool_result" for b in blocks(content)):
        return False
    import re
    return bool(re.sub(r"<system-reminder>.*?</system-reminder>", "", text_content(content), flags=re.S).strip())


class Log:
    """Keep offsets and small request records, never the whole JSONL object graph."""

    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()
        self.agent_id = self.path.stem[6:] if self.path.parent.name == "subagents" else None
        self.session_id = self.path.parent.parent.name if self.agent_id else self.path.stem
        self.id = self.session_id + (":" + self.agent_id if self.agent_id else ":main")
        mp = self.path.with_suffix(".meta.json")
        self.meta = json.loads(mp.read_text()) if mp.exists() else {}
        self.requests = []
        self.offsets = defaultdict(list)
        self.reply_offsets = defaultdict(list)
        self.cwd = None
        self.title = self.meta.get("description") or self.session_id
        self.start = self.end = None
        self.versions = set()
        self.humans = []
        self.compactions = []
        self.tool_locations, self.tool_errors = {}, set()
        self._index()

    def _index(self):
        kinds = ("api-request", "api-request-blob", "api-request-shape", "assistant", "user", "attachment", "custom-title", "summary", "system")
        with self.path.open("rb") as f:
            while True:
                offset = f.tell()
                line = f.readline()
                if not line:
                    break
                if not any(has_type(line, t) for t in kinds):
                    continue
                # Large messages are represented by offsets. Parse once for metadata;
                # drop each object immediately, including base64 and tool outputs.
                d = json.loads(line)
                t = d.get("type")
                if t not in kinds:
                    continue
                self.offsets[t].append(offset)
                ts = d.get("timestamp")
                if ts:
                    self.start = min(self.start or ts, ts)
                    self.end = max(self.end or ts, ts)
                self.cwd = self.cwd or d.get("cwd")
                if d.get("version"):
                    self.versions.add(d["version"])
                if t == "api-request":
                    d["number"] = len(self.requests) + 1
                    d["offset"] = offset
                    self.requests.append(d)
                elif t == "assistant" and d.get("requestRef"):
                    self.reply_offsets[d["requestRef"]].append(offset)
                    for b in d["message"].get("content", []):
                        if b.get("type") == "tool_use":
                            self.tool_locations[b["id"]] = {"offset": offset, "timestamp": ts}
                elif t == "user" and human_message(d):
                    self.humans.append({"offset": offset, "next_request": len(self.requests) + 1, "timestamp": ts})
                    if self.title == self.session_id:
                        self.title = text_content(d["message"]["content"])[:120].replace("\n", " ")
                elif t == "custom-title":
                    self.title = d.get("customTitle") or d.get("title") or self.title
                elif t == "system" and d.get("subtype") == "compact_boundary":
                    self.compactions.append({"offset": offset, "timestamp": ts, "metadata": d.get("compactMetadata")})
                if t == "user":
                    for b in blocks(d.get("message", {}).get("content", [])):
                        if b.get("type") == "tool_result" and b.get("is_error"):
                            self.tool_errors.add(b["tool_use_id"])

    def read(self, offset, handle=None):
        if handle:
            handle.seek(offset)
            return json.loads(handle.readline())
        with self.path.open("rb") as f:
            return self.read(offset, f)

    def latest_human(self, offset):
        return next((x for x in reversed(self.humans) if x["offset"] < offset), None)

    def summary(self):
        return {"id": self.id, "session_id": self.session_id, "agent_id": self.agent_id,
                "path": str(self.path), "title": self.title, "meta": self.meta,
                "cwd": self.cwd, "start": self.start, "end": self.end,
                "start_bjt": local_time(self.start), "end_bjt": local_time(self.end),
                "request_count": len(self.requests), "supported": bool(self.requests and self.offsets["api-request-shape"]),
                "versions": sorted(self.versions)}

    def reply(self, ref, handle):
        chunks, wire, last = [], {}, {}
        for offset in self.reply_offsets.get(ref, []):
            d = self.read(offset, handle)
            chunks.extend((d.get("apiBlockIndex", 0), b) for b in d["message"].get("content", []))
            wire.update(d.get("wireToolInputs") or {})
            last = d
        content = []
        for _, original in sorted(chunks, key=lambda x: x[0]):
            b = dict(original)
            if b.get("type") == "tool_use" and b.get("id") in wire:
                b["input"] = wire[b["id"]]
            content.append(b)
        return {"role": "assistant", "content": content}, last

    def reconstruct(self, start=1, end=None):
        if not self.summary()["supported"]:
            raise ValueError("不支持：记录没有完整的 api-request / api-request-shape")
        end = end or len(self.requests)
        if not (1 <= start <= end <= len(self.requests)):
            raise ValueError("请求范围超出记录")
        selected, current, wanted = [], [], set()
        for req in self.requests[:end]:
            previous = current
            if req["keep"] > len(previous):
                raise ValueError("keep 超过上一请求消息数，记录不完整")
            current = previous[:req["keep"]] + req["tail"]
            if req["number"] >= start:
                r = dict(req)
                r["message_hashes"] = list(current)
                r["removed_hashes"] = previous[req["keep"]:]
                selected.append(r)
                wanted.update(current)
        pool, responses, origins, shapes, result_times = {}, {}, {}, {}, {}
        blob_conflicts = {}
        selected_refs = {r["id"] for r in selected}
        selected_shapes = {r["shapeHash"] for r in selected}

        def add(message, origin=None):
            h = digest(message)
            if h in wanted:
                pool[h] = message
                if origin:
                    origins[h] = origin

        with self.path.open("rb") as f:
            for offset in self.offsets["api-request-blob"]:
                # Hash occurs before the potentially huge message. Filter bytes first.
                f.seek(offset)
                line = f.readline()
                if not any(h.encode() in line[:512] for h in wanted):
                    continue
                d = json.loads(line)
                if d["hash"] in wanted:
                    if digest(d["message"]) != d["hash"]:
                        blob_conflicts[d["hash"]] = digest(d["message"])
                    pool[d["hash"]] = d["message"]
            for offset in self.offsets["api-request-shape"]:
                d = self.read(offset, f)
                if d["shapeHash"] in selected_shapes:
                    shapes[d["shapeHash"]] = d["shape"]
            for ref in self.reply_offsets:
                message, last = self.reply(ref, f)
                add(message, {"kind": "assistant", "request_ref": ref})
                if ref in selected_refs:
                    responses[ref] = {"message": message, "timestamp": last.get("timestamp"),
                                      "model": last.get("message", {}).get("model"),
                                      "usage": last.get("message", {}).get("usage", {}),
                                      "stop_reason": last.get("message", {}).get("stop_reason")}
            run = []

            def flush():
                if run:
                    add({"role": "user", "content": list(run)}, {"kind": "tool_results"})
                    run.clear()

            events = sorted([(o, "user") for o in self.offsets["user"]] +
                            [(o, "flush") for o in self.offsets["assistant"] + self.offsets["api-request"]])
            for offset, kind in events:
                if kind == "flush":
                    flush()
                    continue
                d = self.read(offset, f)
                c = d["message"].get("content")
                if isinstance(c, list) and c and c[0].get("type") == "tool_result":
                    run.extend(c)
                    for b in c:
                        if b.get("type") == "tool_result":
                            result_times[b["tool_use_id"]] = d.get("timestamp")
                elif run and d.get("isMeta") and isinstance(c, (str, list)):
                    run.extend(blocks(c))
                else:
                    m = {"role": "user", "content": c}
                    add(m, {"kind": "human" if human_message(d) else "meta", "offset": offset})
                    add({"role": "user", "content": blocks(c)}, {"kind": "human" if human_message(d) else "meta", "offset": offset})
            flush()
            attachments = []
            for offset in self.offsets["attachment"]:
                d = self.read(offset, f)
                if d.get("rendered"):
                    attachments.append({"attachment": d["attachment"], "rendered": d["rendered"],
                                        "role": d.get("renderedRole", "user"), "timestamp": d.get("timestamp"), "offset": offset})
        missing = sorted(wanted - pool.keys())
        if missing:
            raise ValueError("无法按哈希还原 %d 条消息（不猜测缺失内容）：%s" % (len(missing), ", ".join(h[:12] for h in missing)))
        if selected_shapes - shapes.keys():
            raise ValueError("缺少请求 shape")
        conflicts = [{"kind": "stored_blob_hash_conflict", "expected": h, "actual": digest(pool[h])}
                     for h in blob_conflicts if digest(pool[h]) != h]
        return {"requests": selected, "messages": pool, "responses": responses, "origins": origins, "result_times": result_times,
                "shapes": shapes, "attachments": attachments,
                "verification": {"requests": len(selected), "unique_messages": len(wanted), "hash_mismatches": len(conflicts), "missing_messages": len(missing), "issues": conflicts}}


def paths(projects_dir):
    return sorted(Path(projects_dir).expanduser().glob("**/*.jsonl"))


def candidate_paths(projects_dir, needle):
    """Cheap raw substring pass before decoding any candidate operation."""
    needles = {needle.encode(), json.dumps(needle, ensure_ascii=True)[1:-1].encode()}
    for path in paths(projects_dir):
        with path.open("rb") as f:
            for line in f:
                if has_type(line, "assistant") and any(n in line for n in needles):
                    yield path
                    break
