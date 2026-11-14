"""Normalize reconstructed requests into the documented viewer contract."""
import base64
import copy
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from records import blocks, digest, local_time, packed, text_content
from provenance import comparison, visible_text
from shell import analyze, path_of


GROUPS = {"upstream": "上游交代", "system": "系统提示", "tools": "工具定义",
          "automatic": "自动带上", "files": "读的文件", "commands": "命令和网页输出",
          "reminders": "中途提醒", "outputs": "产出", "requests": "逐次请求",
          "before_range": "范围开始前的对话", "unknown": "没认出来的"}
ATTACHMENTS = {"skill_listing": "skill 列表", "deferred_tools_delta": "延后加载的工具",
               "environment": "环境", "model": "模型", "date": "日期",
               "session_context": "账号", "remote_session_change": "提交署名",
               "agent_listing_delta": "agent 列表", "mcp_instructions_delta": "MCP 说明",
               "auto_mode": "自动模式", "instructions": "指令文件",
               "edited_text_file": "文件被改了", "queued_command": "中途用户消息",
               "plan_mode": "计划模式", "plan_mode_exit": "退出计划模式",
               "hook_blocking_error": "钩子阻止提醒", "silent_turn_reminder": "继续工作提醒",
               "file": "自动附带的文件", "plan_file_reference": "计划文件",
               "skill_mention": "提及的 skill", "compact_file_reference": "压缩后文件引用",
               "invoked_skills": "已调用的 skill", "nested_memory": "目录记忆",
               "task_status": "任务状态", "hook_success": "钩子结果", "hook_system_message": "钩子说明", "read_truncation_notice": "读取截断提醒"}
REMINDERS = {"edited_text_file", "queued_command", "hook_blocking_error", "silent_turn_reminder", "task_status", "plan_mode_exit", "read_truncation_notice"}


class Document:
    def __init__(self, scope, focus):
        self.data = {"schema_version": "1.0", "scope": scope, "nodes": [], "items": {}, "requests": {},
                     "sources": {}, "images": {}, "edges": [], "focus": [],
                     "group_labels": GROUPS, "attachment_labels": ATTACHMENTS}
        self.focus = focus
        # Restored messages/shapes are immutable; avoid rehashing the same large
        # message at every request. Keep the object to prevent id reuse.
        self._source_cache = {}
        self.focus_text = {}
        for p in focus:
            try:
                self.focus_text[p] = Path(p).read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                pass

    def source(self, value):
        cached = self._source_cache.get(id(value))
        if cached is not None and cached[0] is value:
            return cached[1]
        sid = "source:" + digest(value)
        if sid not in self.data["sources"]:
            def encode(v):
                if isinstance(v, list):
                    return [encode(x) for x in v]
                if not isinstance(v, dict):
                    return v
                if v.get("type") == "base64" and isinstance(v.get("data"), str):
                    raw = base64.b64decode(v["data"])
                    h = hashlib.sha256(raw).hexdigest()
                    self.data["images"].setdefault(h, {"id": h, "media_type": v.get("media_type"), "base64": v["data"], "bytes": len(raw)})
                    return dict({k: encode(x) for k, x in v.items() if k != "data"}, data_ref=h)
                return {k: encode(x) for k, x in v.items()}
            self.data["sources"][sid] = encode(value)
        self._source_cache[id(value)] = (value, sid)
        return sid

    def ref(self, value):
        return {"source_id": self.source(value), "pointer": ""}

    def resolve(self, ref):
        value = self.data["sources"][ref["source_id"]]
        for part in ref.get("pointer", "").split("/")[1:]:
            part = part.replace("~1", "/").replace("~0", "~")
            value = value[int(part)] if isinstance(value, list) else value[part]
        if "start" in ref:
            value = value[ref["start"]:ref["end"]]
        return value

    def item(self, node, group, key, label, **fields):
        iid = node["id"] + "/" + group + "/" + digest(key)[:20]
        if iid not in self.data["items"]:
            self.data["items"][iid] = dict(id=iid, node_id=node["id"], group=group, label=label,
                                            first_request=None, request_ids=[], fragments=[], characters=0,
                                            removed_at=[], focus_ids=[], **fields)
            node["groups"][group].append(iid)
        return self.data["items"][iid]

    def node(self, log, mode, start=1, end=None):
        summary = log.summary()
        node = dict(summary, mode=mode, parent_id=None, groups={g: [] for g in GROUPS},
                    request_ids=[], range={"start": start, "end": end or len(log.requests)},
                    context_tokens={"first": None, "last": None}, verification=None)
        self.data["nodes"].append(node)
        return node


class NodeBuilder:
    def __init__(self, doc, log, node, restored):
        self.doc, self.log, self.node, self.r = doc, log, node, restored
        self.calls, self.result_items, self.memo = {}, {}, {}
        self.attachments = {}
        self.rendered_texts, self.added_tools = [], {}
        self.request_numbers = {q["id"]: q["number"] for q in log.requests}
        for attachment in restored["attachments"]:
            for rendered in attachment["rendered"]:
                for block in blocks(rendered["content"]):
                    self.attachments.setdefault(digest(block), attachment)
                    if block.get("type") == "text":
                        core = re.sub(r"^\s*<system-reminder>\s*|\s*</system-reminder>\s*$", "", block["text"]).strip()
                        if core:
                            self.rendered_texts.append((core, attachment))
            definitions = attachment["attachment"].get("surfacedDefinitions", [])
            for definition in definitions if isinstance(definitions, list) else definitions.values():
                if isinstance(definition, dict):
                    self.added_tools[digest(definition.get("definition", definition))] = attachment
        for h, m in restored["messages"].items():
            origin = restored["origins"].get(h, {})
            self.index_calls(m, origin.get("request_ref"))
        for ref, response in restored["responses"].items():
            self.index_calls(response["message"], ref)
        self.before_hashes = set()
        if node["mode"] == "range" and restored["requests"][0]["number"] > 1:
            first = restored["requests"][0]
            human = log.latest_human(first["offset"])
            human_text = text_content(log.read(human["offset"])["message"]["content"]) if human else None
            for h in first["message_hashes"]:
                message = restored["messages"][h]
                if human_text and any(human_text in b.get("text", "") for b in blocks(message["content"])):
                    break
                self.before_hashes.add(h)

    def rid(self, number):
        return self.node["id"] + "/request/" + str(number)

    def index_calls(self, message, request_ref):
        for i, b in enumerate(blocks(message.get("content", []))):
            if b.get("type") != "tool_use":
                continue
            call = {"block": b, "request": self.request_numbers.get(request_ref),
                    "ref": {"source_id": self.doc.source(message), "pointer": "/content/" + str(i)},
                    "timestamp": self.log.tool_locations.get(b["id"], {}).get("timestamp") or next((q["timestamp"] for q in self.log.requests if q["id"] == request_ref), None)}
            if b["name"] == "Bash":
                call["shell"] = analyze(b.get("input", {}).get("command", ""), self.log.cwd)
            self.calls[b["id"]] = call

    def touch(self, item, number, fragment=None):
        item["first_request"] = min(item["first_request"] or number, number)
        rid = self.rid(number)
        if rid not in item["request_ids"]:
            item["request_ids"].append(rid)
        if fragment and fragment not in item["fragments"]:
            item["fragments"].append(fragment)
        return item["id"]

    def generic(self, group, key, label, number, ref, text, **kw):
        item = self.doc.item(self.node, group, key, label, **kw)
        item["characters"] = len(text)
        item.setdefault("display_ref", ref)
        self.touch(item, number, ref)
        return item

    def attach(self, attachment, block, ref, number):
        meta = attachment["attachment"]
        kind = meta["type"]
        tx = block.get("text", "")
        if kind == "instructions" and meta.get("files"):
            raw = self.doc.resolve(ref)
            tx = raw if isinstance(raw, str) else raw.get("text", tx)
            text_pointer = ref["pointer"] if isinstance(raw, str) else ref["pointer"] + "/text"
            base_start = ref.get("start", 0)
            found = []
            for f in meta["files"]:
                pos = tx.find(f["content"])
                if pos >= 0:
                    found.append((pos, f))
            if len(found) == len(meta["files"]):
                found.sort(key=lambda x: x[0])
                owners = []
                for i, (pos, f) in enumerate(found):
                    display = dict(ref, pointer=text_pointer, start=base_start + pos, end=base_start + pos + len(f["content"]))
                    owned = dict(ref, pointer=text_pointer, start=base_start + (0 if i == 0 else pos),
                                 end=base_start + (found[i + 1][0] if i + 1 < len(found) else len(tx)))
                    suffix = {"User": "全局", "Project": "工作区", "AutoMem": "记忆"}.get(f.get("type"), "指令")
                    item = self.generic("automatic", (f["path"], f["content"]), Path(f["path"]).name + "（" + suffix + "）", number, owned, f["content"], kind="attachment", attachment_type=kind, path=f["path"])
                    item["display_ref"] = display
                    item["comparison"] = comparison(f["path"], f["content"], full=True)
                    owners.append((item["id"], owned))
                return owners
        group = "reminders" if kind in REMINDERS else "automatic"
        label = ATTACHMENTS.get(kind, "自动附带：" + kind)
        if kind == "edited_text_file":
            label = Path(meta.get("filename", "文件")).name + " 被改了"
        item = self.generic(group, (kind, attachment["offset"]), label, number, ref, tx, kind="attachment", attachment_type=kind)
        if meta.get("filename"):
            item["path"] = meta["filename"]
        return [(item["id"], ref)]

    def rendered_parts(self, block, ref, number, role):
        if block.get("type") == "tool_addition":
            tool = block.get("tool", {})
            attachment = self.added_tools.get(digest(tool.get("definition", tool)))
            if attachment:
                kind = attachment["attachment"]["type"]
                item = self.doc.item(self.node, "automatic", (kind, attachment["offset"]), ATTACHMENTS.get(kind, kind), kind="attachment", attachment_type=kind)
                self.touch(item, number, ref)
                item.setdefault("tool_definition_refs", []).append(ref)
                item["characters"] += len(json.dumps(block, ensure_ascii=False))
                return [(item["id"], ref)]
            return None
        if block.get("type") != "text":
            return None
        tx, hits = block["text"], []
        for core, attachment in self.rendered_texts:
            if attachment["role"] != role:
                continue
            pos = tx.find(core)
            if pos >= 0:
                hits.append((pos, pos + len(core), attachment))
        if not hits:
            return None
        # Longest matching rendition wins if versions have overlapping text.
        chosen = []
        for hit in sorted(hits, key=lambda x: -(x[1] - x[0])):
            if not any(hit[0] < other[1] and other[0] < hit[1] for other in chosen):
                chosen.append(hit)
        chosen.sort(key=lambda x: x[0])
        # Only wrappers/whitespace may be left over; don't silently absorb an
        # unrecognized neighboring attachment into a known one.
        remaining = tx
        for start, end, _ in reversed(chosen):
            remaining = remaining[:start] + remaining[end:]
        if re.sub(r"</?system-reminder>|\s", "", remaining):
            return None
        result = []
        for i, (start, end, attachment) in enumerate(chosen):
            owned = dict(ref, pointer=ref["pointer"] + "/text" if ref["pointer"].count("/") > 1 else ref["pointer"],
                         start=0 if i == 0 else start, end=chosen[i + 1][0] if i + 1 < len(chosen) else len(tx))
            result.extend(self.attach(attachment, {"type": "text", "text": tx[start:end]}, owned, number))
        return result

    def output(self, call, row):
        b, number = call["block"], call["request"]
        if number is None or not self.node["range"]["start"] <= number <= self.node["range"]["end"]:
            return None
        inp = b.get("input", {})
        item = self.doc.item(self.node, "outputs", row["path"], Path(row["path"]).name, kind="output_file", path=row["path"], writes=[])
        wid = item["id"] + "/write/" + b["id"]
        if not any(w["id"] == wid for w in item["writes"]):
            w = dict(row, id=wid, request=number, request_id=self.rid(number), context_request_id=self.rid(number),
                     tool_use_id=b["id"], timestamp=call["timestamp"], raw_ref=call["ref"],
                     command=inp.get("command"), before_ref=None, after_ref=None, content_ref=None)
            w["is_error"] = b["id"] in self.log.tool_errors
            if b["name"] == "Write":
                w["content_ref"] = dict(call["ref"], pointer=call["ref"]["pointer"] + "/input/content")
            elif 'literal_content' in row:
                w['content_ref'] = self.doc.ref(row['literal_content'])
                w.pop('literal_content', None)
            elif b["name"] == "Edit":
                w["before_ref"] = dict(call["ref"], pointer=call["ref"]["pointer"] + "/input/old_string")
                w["after_ref"] = dict(call["ref"], pointer=call["ref"]["pointer"] + "/input/new_string")
                w["replace_all"] = inp.get("replace_all", False)
            item["writes"].append(w)
            self.touch(item, number, call["ref"])
        return item

    def add_outputs(self):
        for call in self.calls.values():
            b = call["block"]
            inp = b.get("input", {})
            if b["name"] in ("Write", "Edit") and inp.get("file_path"):
                self.output(call, {"path": path_of(inp["file_path"], self.log.cwd), "method": b["name"], "inputs": [], "evidence": "工具参数"})
            elif b["name"] == "Bash":
                for row in call["shell"]["writes"]:
                    self.output(call, row)

    def file(self, row, call, result, number, ref, shared):
        path = row["path"]
        item = self.doc.item(self.node, "files", path, Path(path).name, kind="file", path=path, reads=[], image_ids=[])
        tid = result["tool_use_id"]
        occurrence_id = item["id"] + "/read/" + tid
        if not any(r["id"] == occurrence_id for r in item["reads"]):
            text = text_content(result.get("content", ""))
            if row.get('result_text_slice'):
                part = row['result_text_slice']
                text = text[part['start']:part['end']]
            visible, truncated = visible_text(text, row["method"])
            coverage = copy.deepcopy(row["coverage"])
            if truncated:
                coverage.update(kind="partial", label=truncated["label"])
            images = []
            for block in blocks(result.get("content", [])):
                if block.get("type") == "image" and block.get("source", {}).get("type") == "base64":
                    images.append(hashlib.sha256(base64.b64decode(block["source"]["data"])).hexdigest())
            occurrence = {"id": occurrence_id, "request": number, "request_id": self.rid(number),
                          "call_request_id": self.rid(call["request"]) if call.get("request") else None,
                          "tool_use_id": tid, "timestamp": self.r["result_times"].get(tid) or call.get("timestamp"),
                          "method": row["method"], "command": call["block"].get("input", {}).get("command"),
                          "call_ref": call["ref"], "raw_ref": ref, "visible_ref": self.doc.ref(visible),
                          "coverage": coverage, "truncation": truncated, "characters": len(text),
                          "shared_with": shared, "image_ids": images, "producer_edge_ids": [],
                          "recognition": row.get("recognition"), "removed_at": []}
            occurrence.update(result_text_slice=row.get('result_text_slice'),
                              call_failed=bool(result.get('is_error')),
                              is_error=bool(result.get('is_error')) and not bool(row.get('result_text_slice')))
            occurrence["comparison"] = comparison(path, visible, full=coverage["kind"] == "full", image_hashes=images, shared=bool(shared), read_timestamp=occurrence["timestamp"])
            item["reads"].append(occurrence)
            item["image_ids"] = list(dict.fromkeys(item["image_ids"] + images))
            item["characters"] += len(text)
            item["read_count"] = len(item["reads"])
        self.touch(item, number, ref)
        return item

    def recognize(self, text, existing):
        rows = []
        for path, content in self.doc.focus_text.items():
            if path in existing or not content.strip():
                continue
            if content in text:
                rows.append({"path": path, "method": "按内容认出", "coverage": {"kind": "full", "label": "当前全文逐字命中", "selectors": []}, "recognition": {"matched_lines": list(range(1, len(content.splitlines()) + 1)), "matched_characters": len(content)}})
                continue
            hits = [(i + 1, line) for i, line in enumerate(content.splitlines()) if len(line.strip()) >= 12 and line in text]
            if len(hits) >= 2 and sum(len(line) for _, line in hits) >= 80:
                rows.append({"path": path, "method": "按内容认出", "coverage": {"kind": "partial", "label": "部分行逐字命中", "selectors": []}, "recognition": {"matched_lines": [i for i, _ in hits], "matched_characters": sum(len(line) for _, line in hits)}})
        return rows

    def tool_result(self, block, ref, number):
        tid = block["tool_use_id"]
        call = self.calls.get(tid)
        text = text_content(block.get("content", ""))
        if call is None:
            item = self.generic("unknown", (tid, ref), "找不到来源的工具结果", number, ref, text, kind="unmatched_tool_result")
            return [(item["id"], ref)]
        name = call["block"]["name"]
        inp = call["block"].get("input", {})
        rows = []
        if not block.get("is_error"):
            if name == "Read" and inp.get("file_path"):
                partial = bool(inp.get("offset") or inp.get("limit"))
                rows = [{"path": path_of(inp["file_path"], self.log.cwd), "method": "Read", "coverage": {"kind": "partial" if partial else "full", "label": "Read 第 %s 行起，%s 行" % (inp.get("offset", 1), inp.get("limit", "至末尾")) if partial else "全文", "selectors": [{"method": "Read", "offset": inp.get("offset"), "limit": inp.get("limit")}]}}]
            elif name == "Bash":
                rows = copy.deepcopy(call["shell"]["reads"])
        elif name == 'Bash':
            # A later shell error does not retract earlier stdout. Recover
            # only reads whose entire current text occurs verbatim in that
            # recorded output, in command order; existence alone proves none.
            cursor = 0
            for candidate in call['shell']['reads']:
                if candidate['coverage']['kind'] != 'full':
                    continue
                try:
                    with Path(candidate['path']).open('rb') as f:
                        raw = f.read(1024 * 1024 + 1)
                    if len(raw) > 1024 * 1024:
                        continue
                    content = raw.decode('utf-8').rstrip('\n')
                except (OSError, UnicodeError):
                    continue
                pos = text.find(content, cursor) if content else -1
                if pos >= 0:
                    row = copy.deepcopy(candidate)
                    row['result_text_slice'] = {'start': pos, 'end': pos + len(content)}
                    row['recognition'] = {'basis': '失败调用的输出中逐字命中当前全文', 'matched_characters': len(content)}
                    rows.append(row)
                    cursor = pos + len(content)
        existing = {r["path"] for r in rows}
        # 按内容认出焦点文件，只用在认不出读了哪个文件的调用上。调用已经明确读了某个文件时，
        # 输出里出现焦点文件的内容，只说明两份文件内容一样（比如快照副本），不算又读了焦点文件。
        if not rows:
            rows.extend(self.recognize(visible_text(text, "Read" if name == "Read" else "")[0], existing))
        owners = []
        for row in rows:
            item = self.file(row, call, block, number, ref, [r["path"] for r in rows if r["path"] != row["path"]])
            owners.append((item["id"], ref))
        if not owners and name in ("Write", "Edit") and inp.get("file_path"):
            item = self.output(call, {"path": path_of(inp["file_path"], self.log.cwd), "method": name, "inputs": [], "evidence": "工具参数"})
            if item:
                item.setdefault("receipts", []).append({"request_id": self.rid(number), "raw_ref": ref, "is_error": block.get("is_error", False)})
                self.touch(item, number, ref)
                owners = [(item["id"], ref)]
        if not owners:
            label = name + " 输出"
            item = self.generic("commands", tid, label, number, ref, text, kind="tool_output", tool=name)
            item.update(command=inp.get("command"), call_ref=call["ref"], tool_use_id=tid,
                        truncation=visible_text(text)[1], is_error=block.get("is_error", False))
            item["possible_outputs"] = [w for w in call.get("shell", {}).get("writes", []) if w.get("confidence") == "ambiguous_argument"]
            owners = [(item["id"], ref)]
        self.result_items[tid] = owners
        return owners

    def classify(self, h, index, block, number):
        key = (h, index)
        if key in self.memo:
            return self.memo[key]
        message = self.r["messages"][h]
        pointer = "/content/" + str(index) if isinstance(message["content"], list) else "/content"
        ref = {"source_id": self.doc.source(message), "pointer": pointer}
        tx = block.get("text", "")
        if h in self.before_hashes:
            item = self.doc.item(self.node, "before_range", "before", "范围开始前的对话", kind="prior_conversation")
            self.touch(item, number, ref)
            item["characters"] += len(tx) if block.get("type") == "text" else len(packed(block))
            result = [(item["id"], ref)]
        elif digest(block) in self.attachments:
            result = self.attach(self.attachments[digest(block)], block, ref, number)
        elif message["role"] != "assistant" and (parts := self.rendered_parts(block, ref, number, message["role"])):
            result = parts
        elif message["role"] == "assistant":
            origin = self.r["origins"].get(h, {})
            response_no = self.request_numbers.get(origin.get("request_ref"))
            item = self.generic("requests", h, "第 %s 次的模型回复" % (response_no or "未知"), response_no or number, ref, text_content(blocks(message["content"])), kind="response", response_request_id=self.rid(response_no) if response_no else None)
            item["display_ref"] = {"source_id": self.doc.source(message), "pointer": ""}
            result = [(item["id"], ref)]
        elif block.get("type") == "tool_result":
            result = self.tool_result(block, ref, number)
        elif tx.startswith("[Image: original") or ("[Image: original" in tx and self.result_items):
            preceding = blocks(message["content"])[:index]
            tid = next((b.get("tool_use_id") for b in reversed(preceding) if b.get("type") == "tool_result"), None)
            result = [(iid, ref) for iid, _ in self.result_items.get(tid, [])]
            if not result:
                item = self.generic("reminders", key, "图片尺寸说明", number, ref, tx, kind="image_description")
                result = [(item["id"], ref)]
        else:
            origin = self.r["origins"].get(h, {})
            if number == self.node["range"]["start"] and tx.strip().startswith("<system-reminder>"):
                named_tools = [self.doc.data["items"][i] for i in self.node["groups"]["tools"] if re.search(r"\b" + re.escape(self.doc.data["items"][i]["label"]) + r"\b", tx)]
                if len(named_tools) == 1:
                    item = named_tools[0]
                    item.setdefault("usage_instruction_refs", []).append(ref)
                    item["supplementary_characters"] = item.get("supplementary_characters", 0) + len(tx)
                    self.touch(item, number, ref)
                    result = [(item["id"], ref)]
                    self.memo[key] = result
                    return result
            group = "upstream" if message["role"] == "user" and not tx.strip().startswith("<system-reminder>") and origin.get("kind") != "meta" else "reminders" if origin.get("kind") == "meta" or tx.strip().startswith("<system-reminder>") else "unknown"
            label = "派活 prompt" if group == "upstream" and self.log.agent_id else "你的消息" if group == "upstream" else "中途提醒" if group == "reminders" else "未匹配来源"
            item = self.generic(group, key, label, number, ref, tx, kind="message")
            result = [(item["id"], ref)]
        self.memo[key] = result
        return result

    def build(self):
        self.add_outputs()
        previous_items = set()
        for req in self.r["requests"]:
            number, rid = req["number"], self.rid(req["number"])
            shape = self.r["shapes"][req["shapeHash"]]
            shape_sid = self.doc.source(shape)
            context, ownership = [], []
            system = shape.get("system", [])
            item = self.generic("system", digest(system), "系统提示", number, {"source_id": shape_sid, "pointer": "/system"}, text_content(system), kind="system")
            context.append(item["id"])
            ownership.append({"location": "system", "owner_id": item["id"], "related_ids": [], "raw_ref": item["display_ref"]})
            for i, tool in enumerate(shape.get("tools", [])):
                tr = {"source_id": shape_sid, "pointer": "/tools/" + str(i)}
                item = self.generic("tools", digest(tool), tool.get("name", "工具"), number, tr, json.dumps(tool, ensure_ascii=False), kind="tool_definition")
                context.append(item["id"])
                ownership.append({"location": "tools/" + str(i), "owner_id": item["id"], "related_ids": [], "raw_ref": tr})
            for mi, h in enumerate(req["message_hashes"]):
                message = self.r["messages"][h]
                for bi, block in enumerate(blocks(message["content"])):
                    owners = self.classify(h, bi, block, number)
                    context.extend(iid for iid, _ in owners)
                    # Shared output has one canonical owner and additional links;
                    # instruction text is genuinely partitioned into disjoint slices.
                    partitioned = len(owners) > 1 and all("start" in ref for _, ref in owners)
                    selected = owners if partitioned else owners[:1]
                    for si, (iid, ref) in enumerate(selected):
                        ownership.append({"location": "messages/%d/content/%d%s" % (mi, bi, "/slice/%d" % si if partitioned else ""),
                                          "owner_id": iid, "related_ids": [] if partitioned else [x for x, _ in owners[1:]], "raw_ref": ref})
                for key in message.keys() - {"role", "content"}:
                    metadata_ref = {"source_id": self.doc.source(message), "pointer": "/" + key.replace("~", "~0").replace("/", "~1")}
                    ownership.append({"location": "messages/%d/%s" % (mi, key), "owner_id": owners[0][0], "related_ids": [], "raw_ref": metadata_ref})
                    item = self.doc.data["items"][owners[0][0]]
                    if metadata_ref not in item["fragments"]:
                        item["fragments"].append(metadata_ref)
            response = self.r["responses"].get(req["id"], {})
            usage = response.get("usage") or {}
            tokens = sum(usage.get(k, 0) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")) if usage else None
            context = list(dict.fromkeys(context))
            removed = sorted(previous_items - set(context))
            for iid in removed:
                self.doc.data["items"][iid]["removed_at"].append(rid)
            response_ref = self.doc.ref(response["message"]) if response.get("message") else None
            previous_offset = self.log.requests[number - 2]["offset"] if number > 1 else -1
            compactions = [c for c in self.log.compactions if previous_offset < c["offset"] < req["offset"]]
            request = {"id": rid, "node_id": self.node["id"], "number": number, "api_request_id": req["id"],
                       "timestamp": req["timestamp"], "timestamp_bjt": local_time(req["timestamp"]),
                       "query_source": req.get("querySource"), "params": req.get("params", {}),
                       "shape_ref": {"source_id": shape_sid, "pointer": ""},
                       "message_source_ids": [self.doc.source(self.r["messages"][h]) for h in req["message_hashes"]],
                       "message_hashes": req["message_hashes"], "new_message_source_ids": [self.doc.source(self.r["messages"][h]) for h in req["tail"]],
                       "keep": req["keep"], "response_ref": response_ref, "usage": usage, "context_tokens": tokens,
                       "context_item_ids": context, "ownership": ownership,
                       "new_item_ids": [x for x in context if x not in previous_items],
                       "cleanup": {"changed": bool(req["removed_hashes"] or compactions), "kind": "compaction" if compactions else "keep_reduced" if req["removed_hashes"] else None,
                                   "compactions": compactions, "removed_message_hashes": req["removed_hashes"], "removed_item_ids": removed},
                       "verification": {"hash_mismatches": sum(h != digest(self.r["messages"][h]) for h in set(req["message_hashes"])), "missing_messages": 0}}
            self.doc.data["requests"][rid] = request
            self.node["request_ids"].append(rid)
            if response_ref:
                item = self.generic("requests", digest(response["message"]), "第 %d 次的模型回复" % number, number, response_ref, text_content(response["message"]["content"]), kind="response", response_request_id=rid)
                item["display_ref"] = response_ref
            previous_items = set(context)
        self.node["verification"] = self.r["verification"]
        self.node["context_tokens"] = {"first": self.doc.data["requests"][self.node["request_ids"][0]]["context_tokens"], "last": self.doc.data["requests"][self.node["request_ids"][-1]]["context_tokens"]}
        self.node["start"] = self.r["requests"][0]["timestamp"]
        final_response = self.r["responses"].get(self.r["requests"][-1]["id"], {})
        self.node["end"] = final_response.get("timestamp") or self.r["requests"][-1]["timestamp"]
        self.node["start_bjt"], self.node["end_bjt"] = local_time(self.node["start"]), local_time(self.node["end"])
        self.finalize_files()
        self.handback()
        return self.node

    def finalize_files(self):
        for iid in self.node["groups"]["files"]:
            item = self.doc.data["items"][iid]
            item["reads"].sort(key=lambda r: r["request"])
            item["comparison"] = item["reads"][-1]["comparison"]
            item["status"] = "读全了" if any(r["coverage"]["kind"] == "full" for r in item["reads"]) else "读了一部分"
            for read in item["reads"]:
                sid = read["raw_ref"]["source_id"]
                present = False
                for rid in self.node["request_ids"]:
                    req = self.doc.data["requests"][rid]
                    now = sid in req["message_source_ids"]
                    if present and not now:
                        read["removed_at"].append(rid)
                    present = now
        for iid in self.node["groups"]["outputs"]:
            item = self.doc.data["items"][iid]
            if item.get("kind") != "output_file":
                continue
            writes = sorted(item["writes"], key=lambda w: w["request"])
            item["writes"] = writes
            successful = [w for w in writes if not w["is_error"]]
            if not successful:
                item["comparison"] = comparison(item["path"])
                item["comparison"]["evidence_id"] = None
                continue
            final = successful[-1]
            text, basis = None, None
            if final.get("content_ref") and final.get('content_kind') != 'append':
                text = self.doc.resolve(final["content_ref"])
                basis = final["id"]
            reads = [r for fid in self.node["groups"]["files"] if self.doc.data["items"][fid]["path"] == item["path"] for r in self.doc.data["items"][fid]["reads"] if r["request"] > final["request"] and r["coverage"]["kind"] == "full" and not r["shared_with"]]
            if reads:
                text = self.doc.resolve(reads[-1]["visible_ref"])
                basis = reads[-1]["id"]
            item["comparison"] = comparison(item["path"], text, full=True)
            item["comparison"]["evidence_id"] = basis
            item["characters"] = len(text) if text is not None else 0

    def handback(self):
        if not self.log.agent_id:
            return
        for req in reversed(self.r["requests"]):
            response = self.r["responses"].get(req["id"], {})
            message = response.get("message", {})
            for i, b in enumerate(message.get("content", [])):
                if b.get("type") == "tool_use" and b.get("name") == "SubagentHandback":
                    ref = {"source_id": self.doc.source(message), "pointer": "/content/%d/input/message" % i}
                    item = self.generic("outputs", "handback", "交回主会话的话", req["number"], ref, b.get("input", {}).get("message", ""), kind="handback")
                    item["context_request_id"] = self.rid(req["number"])
                    return
            text = text_content(message.get("content", []))
            if text:
                ref = self.doc.ref(message)
                item = self.generic("outputs", "handback", "交回主会话的话", req["number"], ref, text, kind="handback")
                item["context_request_id"] = self.rid(req["number"])
                return
