#!/usr/bin/env python3
"""Trace Claude Code request context without executing recorded commands."""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Isolated Python omits the script directory; add only this trusted directory.
_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from model import ATTACHMENTS, Document, GROUPS, NodeBuilder
from provenance import Catalog, focus_paths
from records import BJT, blocks, digest, has_type, local_time, paths, text_content


def display_time(value):
    return datetime.fromisoformat(local_time(value)).strftime("%m-%d %H:%M") if value else "未知"


def display_range(start, end):
    first, last = local_time(start), local_time(end)
    if first and last and first[:10] == last[:10]:
        return display_time(start) + "–" + datetime.fromisoformat(last).strftime("%H:%M")
    return display_time(start) + "–" + display_time(end)


def date_bound(value, end=False):
    if not value:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=BJT)
    if end and len(value) == 10:
        from datetime import timedelta
        dt += timedelta(days=1)
    return dt


def in_dates(log, since=None, until=None):
    start, end = date_bound(log.start), date_bound(log.end)
    return bool(start and end and (not since or end >= date_bound(since)) and (not until or start < date_bound(until, True)))


def list_logs(args):
    catalog = Catalog(args.projects_dir)
    all_paths = paths(args.projects_dir)
    families = {}
    for p in all_paths:
        root = p.parent.parent if p.parent.name == "subagents" else p.with_suffix("")
        families.setdefault(root, []).append(p)
    for root, members in sorted(families.items()):
        parent_path = root.with_suffix(".jsonl")
        # Metadata-only prefilter for descriptions; titles/cwd are checked on
        # their own JSONL entries, not by grepping private tool output text.
        selected = []
        main_match = False
        if parent_path.exists():
            main = catalog.log(parent_path)
            main_match = not args.grep or args.grep.casefold() in (main.title + " " + (main.cwd or "")).casefold()
        else:
            main = None
        for p in members:
            if p == parent_path:
                continue
            mp = p.with_suffix(".meta.json")
            meta = json.loads(mp.read_text()) if mp.exists() else {}
            description_match = args.grep and args.grep.casefold() in meta.get("description", "").casefold()
            if not main_match and not description_match and args.grep:
                # cwd can differ from the parent. It occurs near the start.
                with p.open("rb") as f:
                    first = next((json.loads(line) for line in f if has_type(line, "user") or has_type(line, "assistant")), {})
                if args.grep.casefold() not in first.get("cwd", "").casefold():
                    continue
            child = catalog.log(p)
            if in_dates(child, args.since, args.until):
                selected.append(child)
        if not selected and not (main and main_match and in_dates(main, args.since, args.until)):
            continue
        if main:
            s = main.summary()
            print("%s  %s  %s–%s  %s 次请求  %s" % (s["session_id"], s["title"], display_time(s["start"]), display_time(s["end"]), format(s["request_count"], ","), "有完整请求记录" if s["supported"] else "不支持：没有完整请求记录"))
        for child in sorted(selected, key=lambda x: x.start or ""):
            s = child.summary()
            print("  %s  %s  %s–%s  %s 次请求" % (s["agent_id"], s["title"], display_time(s["start"]), display_time(s["end"]), format(s["request_count"], ",")))


def find_file(args):
    found = Catalog(args.projects_dir).find(args.file)
    if args.json:
        print(json.dumps(found, ensure_ascii=False, indent=2))
    else:
        for op in found:
            # Deliberately omit command text from stdout. The JSON and data
            # artifact retain it in full for local inspection.
            print("%s  %s  第 %s 次  %s  %s  %s%s" % (op["session_id"], Path(op["node_path"]).stem, op["request"], op["method"], op["evidence"], display_time(op["timestamp"]), "  " + Path(op["script"]).name if op.get("script") else ""))
    return 0 if found else 1


def add_dispatch(doc, parent_node, child_node, dispatch):
    parent, req, block = dispatch["parent"], dispatch["request"], dispatch["block"]
    number = req["number"]
    rid = parent.id + "/request/" + str(number)
    inp = block.get("input", {})
    raw_ref = doc.ref(block)
    item = doc.item(parent_node, "upstream", block["id"], "派活 prompt → " + child_node["title"], kind="dispatch",
                    description=inp.get("description"), model=inp.get("model", child_node["meta"].get("model")), child_id=child_node["id"])
    item.update(first_request=number, characters=len(inp.get("prompt", "")), request_ids=[rid],
                display_ref=dict(raw_ref, pointer="/input/prompt"), fragments=[raw_ref])
    if rid not in doc.data["requests"]:
        doc.data["requests"][rid] = {"id": rid, "node_id": parent.id, "number": number,
                                     "timestamp": req["timestamp"], "timestamp_bjt": local_time(req["timestamp"]),
                                     "stub": True, "dispatch_item_ids": [item["id"]],
                                     "context_item_ids": [], "response_ref": raw_ref}
        parent_node["request_ids"].append(rid)
    else:
        doc.data["requests"][rid].setdefault("dispatch_item_ids", []).append(item["id"])
    if dispatch.get("human"):
        message = dispatch["human"]["message"]
        human = doc.item(parent_node, "upstream", ("human", digest(message)), "你的消息（派活前最近一条）", kind="human_message")
        human.update(characters=len(text_content(message["content"])), display_ref=doc.ref(message), timestamp=dispatch["human"].get("timestamp"))
    child_node["parent_id"] = parent.id
    child_prompt = next((doc.data["items"][iid] for iid in child_node["groups"]["upstream"] if doc.data["items"][iid].get("label") == "派活 prompt"), None)
    if child_prompt:
        child_prompt.update(parent_node_id=parent.id, parent_request_id=rid, dispatch_item_id=item["id"],
                            description=inp.get("description"), model=inp.get("model", child_node["meta"].get("model")))
    edge = {"id": "dispatch:" + block["id"], "kind": "dispatch", "parent_node_id": parent.id,
            "child_node_id": child_node["id"], "parent_request_id": rid, "parent_item_id": item["id"],
            "child_item_id": child_prompt["id"] if child_prompt else None, "tool_use_id": block["id"],
            "description": inp.get("description"), "model": inp.get("model", child_node["meta"].get("model")),
            "prompt_ref": dict(raw_ref, pointer="/input/prompt"), "timestamp": dispatch["timestamp"]}
    doc.data["edges"].append(edge)
    if parent_node["mode"] == "dispatch":
        ts = dispatch["timestamp"]
        if not parent_node.get("dispatch_times"):
            parent_node["dispatch_times"] = []
        parent_node["dispatch_times"].append(ts)
        parent_node["start"], parent_node["end"] = min(parent_node["dispatch_times"]), max(parent_node["dispatch_times"])
        parent_node["start_bjt"], parent_node["end_bjt"] = local_time(parent_node["start"]), local_time(parent_node["end"])
        numbers = [doc.data["requests"][r]["number"] for r in parent_node["request_ids"]]
        parent_node["range"] = {"start": min(numbers), "end": max(numbers)}


def finalize(doc):
    d = doc.data
    for path, roots in doc.focus.items():
        links, reads, auto, executed = [], [], [], []
        fid = "focus:" + digest(path)[:20]
        for item in d["items"].values():
            if item.get("path") == path and item["group"] in ("files", "automatic"):
                item["focus_ids"].append(fid)
                links.append(item["id"])
                reads.extend(item.get("reads", []))
                if item["group"] == "automatic":
                    auto.append(item)
        for node in d["nodes"]:
            executed.extend({"node_id": node["id"], **x} for x in node.get("executed_files", []) if x["path"] == path)
        full = any(r["coverage"]["kind"] == "full" for r in reads) or bool(auto)
        comps = [r["comparison"] for r in reads] + [x["comparison"] for x in auto if x.get("comparison")]
        comparison_status = "different" if any(c["status"] == "different" for c in comps) else comps[-1]["status"] if comps else "unavailable"
        d["focus"].append({"id": fid, "path": path, "roots": roots, "item_ids": links,
                           "status": "读全了" if full else "读了一部分" if reads else "只运行过没读内容" if executed else "没读到",
                           "read_count": len(reads), "first_request": min((r["request"] for r in reads), default=min((a["first_request"] for a in auto), default=None)),
                           "comparison_status": comparison_status, "executions": executed})
    for node in d["nodes"]:
        last = next((d["requests"][rid] for rid in reversed(node["request_ids"]) if not d["requests"][rid].get("stub")), None)
        stats = {g: {"items": len(node["groups"][g]), "characters": sum(d["items"][i]["characters"] for i in node["groups"][g]), "last_context_items": 0, "last_context_characters": 0} for g in GROUPS}
        if last:
            seen = set()
            locations = [o["location"] for o in last["ownership"]]
            if len(locations) != len(set(locations)):
                raise ValueError("上下文归属重复")
            for own in last["ownership"]:
                item = d["items"][own["owner_id"]]
                value = doc.resolve(own["raw_ref"])
                chars = len(value) if isinstance(value, str) else len(text_content([value])) if isinstance(value, dict) and value.get("type") == "text" else len(json.dumps(value, ensure_ascii=False))
                stats[item["group"]]["last_context_characters"] += chars
                if item["id"] not in seen:
                    stats[item["group"]]["last_context_items"] += 1
                    seen.add(item["id"])
            node["verification"].update(ownership_locations=len(locations), unclassified_items=len(node["groups"]["unknown"]))
        node["group_stats"] = stats
    d["nodes"].sort(key=lambda n: (n["start"] or "", n["id"]))
    d["scope"].update(node_count=len(d["nodes"]), start=min(n["start"] for n in d["nodes"] if n["start"]), end=max(n["end"] for n in d["nodes"] if n["end"]))
    d["scope"].update(start_bjt=local_time(d["scope"]["start"]), end_bjt=local_time(d["scope"]["end"]))
    d["scope"]["verification"] = {"hash_mismatches": sum((n["verification"] or {}).get("hash_mismatches", 0) for n in d["nodes"]),
                                    "missing_messages": sum((n["verification"] or {}).get("missing_messages", 0) for n in d["nodes"]),
                                    "unclassified_items": sum(len(n["groups"]["unknown"]) for n in d["nodes"])}


def build(args):
    catalog = Catalog(args.projects_dir)
    focus = focus_paths(args.focus or [])
    scope = {"from_output": str(Path(args.from_output).expanduser().resolve()) if args.from_output else None,
             "named_nodes": args.node or [], "focus_arguments": args.focus or [], "since": args.since, "until": args.until,
             "selection_policy": "排除晚于文件修改时间的写入；明确写入优先于参数推断，同类按时间倒序，选择首项", "candidates": []}
    doc = Document(scope, focus)
    selected, dispatches = {}, {}

    def select(log, bounds=None):
        if log.id not in selected:
            selected[log.id] = (log, bounds)

    for p in args.node or []:
        log = catalog.log(p)
        bounds = tuple(map(int, args.range.split("-"))) if args.range and not log.agent_id else None
        select(log, bounds)
    if args.from_output:
        found = catalog.find(args.from_output)
        if not found:
            raise ValueError("没有找到写入这个文件的操作")
        scope["candidates"] = [{k: op[k] for k in ("node_id", "node_path", "request", "method", "evidence", "timestamp", "tool_use_id")} for op in found]
        chosen = found[0]
        scope["selected_tool_use_id"] = chosen["tool_use_id"]
        log = catalog.log(chosen["node_path"])
        bounds = None
        if not log.agent_id:
            human = log.latest_human(chosen["offset"])
            bounds = (human["next_request"] if human else 1, chosen["request"])
            if args.range:
                bounds = tuple(map(int, args.range.split("-")))
        select(log, bounds)
    prebuilt = {}
    if not selected and focus:
        for p in paths(args.projects_dir):
            log = catalog.log(p)
            if not in_dates(log, args.since, args.until) or not log.summary()["supported"]:
                continue
            matching_numbers = [r["number"] for r in log.requests if in_dates(type("Span", (), {"start": r["timestamp"], "end": r["timestamp"]})(), args.since, args.until)]
            if not matching_numbers:
                continue
            bounds = None if log.agent_id else (matching_numbers[0], matching_numbers[-1])
            restored = log.reconstruct(*(bounds or (1, None)))
            probe = Document(scope.copy(), focus)
            node = probe.node(log, "full" if log.agent_id else "range", *(bounds or (1, None)))
            builder = NodeBuilder(probe, log, node, restored)
            builder.build()
            if any(item.get("path") in focus and item["group"] in ("files", "automatic") for item in probe.data["items"].values()):
                select(log, bounds)
                prebuilt[log.id] = restored
    if not selected:
        raise ValueError("没有选中节点：请指定 --node、--from-output，或有匹配记录的 --focus")
    built = {}
    pending = list(selected)
    while pending:
        nid = pending.pop(0)
        if nid in built:
            continue
        log, bounds = selected[nid]
        restored = prebuilt.pop(nid, None) or log.reconstruct(*(bounds or (1, None)))
        node = doc.node(log, "full" if log.agent_id else "range", *(bounds or (1, None)))
        builder = NodeBuilder(doc, log, node, restored)
        builder.build()
        node["executed_files"] = [{"path": p, "request_id": builder.rid(c["request"]), "call_ref": c["ref"]} for c in builder.calls.values() if c.get("request") and node["range"]["start"] <= c["request"] <= node["range"]["end"] for p in c.get("shell", {}).get("executed", [])]
        built[nid] = node
        if log.agent_id:
            dispatch = catalog.parent(log)
            if dispatch:
                dispatches[nid] = dispatch
                parent = dispatch["parent"]
                if parent.agent_id and parent.id not in selected:
                    select(parent)
                    pending.append(parent.id)
        if args.from_output:
            writes = catalog.family_writes(log)
            for iid in node["groups"]["files"]:
                for read in doc.data["items"][iid]["reads"]:
                    earlier = [w for w in writes.get(doc.data["items"][iid]["path"], []) if w["timestamp"] < (read["timestamp"] or "")]
                    if earlier and earlier[-1]["node_id"] != nid and not earlier[-1]["node_id"].endswith(":main"):
                        source = catalog.log(earlier[-1]["node_path"])
                        if source.id not in selected:
                            select(source)
                            pending.append(source.id)
    # Restore only the main agent interval from the nearest user message before
    # the first selected dispatch through the last selected dispatch.
    parents = {}
    for dispatch in dispatches.values():
        parent = dispatch['parent']
        if parent.id not in built:
            parents.setdefault(parent.id, []).append(dispatch)
    for pid, calls in parents.items():
        parent = calls[0]['parent']
        first = min(calls, key=lambda c: c['request']['number'])['request']
        human = parent.latest_human(first['offset'])
        start = human['next_request'] if human else first['number']
        end = max(c['request']['number'] for c in calls)
        node = doc.node(parent, 'range', start, end)
        NodeBuilder(doc, parent, node, parent.reconstruct(start, end)).build()
        built[pid] = node
    for child_id, dispatch in dispatches.items():
        parent = dispatch["parent"]
        if parent.id not in built:
            built[parent.id] = doc.node(parent, "dispatch")
        add_dispatch(doc, built[parent.id], built[child_id], dispatch)
    # Link file versions only after every included producer has been built.
    for node in list(doc.data["nodes"]):
        if node["mode"] == "dispatch":
            continue
        timelines = catalog.family_writes(catalog.log(node["path"]))
        for iid in node["groups"]["files"]:
            item = doc.data["items"][iid]
            producers = [other for other in doc.data["items"].values() if other["group"] == "outputs" and other.get("path") == item["path"] and other["node_id"] != node["id"] and other["node_id"].split(":")[0] == node["session_id"]]
            for read in item["reads"]:
                earlier = [w for w in timelines.get(item["path"], []) if w["timestamp"] < (read["timestamp"] or "")]
                latest_id = earlier[-1]["tool_use_id"] if earlier else None
                candidates = [(w, prod) for prod in producers for w in prod["writes"] if w["tool_use_id"] == latest_id]
                if not candidates:
                    continue
                version, prod = max(candidates, key=lambda x: (x[0]["timestamp"], x[0]["request"]))
                eid = "flow:" + digest((version["id"], read["id"]))[:20]
                edge = {"id": eid, "kind": "file_flow", "path": item["path"], "producer_node_id": prod["node_id"], "producer_item_id": prod["id"],
                        "write_ids": [w["id"] for w in prod["writes"]], "version_write_id": version["id"], "version_request_id": version["request_id"],
                        "consumer_node_id": node["id"], "consumer_item_id": iid, "read_id": read["id"], "read_request_id": read["request_id"]}
                doc.data["edges"].append(edge)
                read["producer_edge_ids"].append(eid)
                prod.setdefault("consumer_edge_ids", []).append(eid)
    finalize(doc)
    from chain import upgrade
    upgrade(doc)
    return doc.data


def tree(data):
    if data.get('schema_version') == '2.0':
        from chain import render_tree
        return render_tree(data, display_range)
    scope = data["scope"]
    name = " / ".join(Path(scope["from_output"]).parent.parts[-2:]) if scope.get("from_output") else "上下文链路"
    lines = ["%s · %s 个节点 · %s（北京时间）" % (name, format(scope["node_count"], ","), display_range(scope["start_bjt"], scope["end_bjt"]))]
    if data["focus"]:
        read = sum(x["status"] in ("读全了", "读了一部分") for x in data["focus"])
        lines.append("├─ ★ 关注 · 读到 %s / %s 个文件" % (format(read, ","), format(len(data["focus"]), ",")))
        read_files = [f for f in data["focus"] if f["status"] in ("读全了", "读了一部分")]
        executed_only = [f for f in data["focus"] if f["status"] == "只运行过没读内容"]
        unread = [f for f in data["focus"] if f["status"] == "没读到"]
        for f in read_files + executed_only:
            lines.append("│  ├─ %s · %s · %s" % (f["path"], f["status"], {"same": "和现在一致", "different": "和现在不一致", "missing": "文件已不在", "unavailable": "没法比"}[f["comparison_status"]]))
        if unread:
            lines.append("│  └─ 没读到 %s 个" % format(len(unread), ","))
            for f in unread:
                label = Path(f["path"]).name
                for root in f["roots"]:
                    if f["path"] != root:
                        try:
                            label = str(Path(f["path"]).relative_to(root))
                            break
                        except ValueError:
                            pass
                lines.append("│     ├─ " + label)
    children = {}
    nodes = {n["id"]: n for n in data["nodes"]}
    for node in data["nodes"]:
        parent = node["parent_id"]
        # Main dispatch is a peer of its child, as in the agreed MVP tree.
        nested = parent if parent and nodes[parent].get("agent_id") else None
        children.setdefault(nested, []).append(node)

    def emit(node, prefix=""):
        tokens = node["context_tokens"]
        head = "主会话 · 只取派活" if node["mode"] == "dispatch" else "%s · %s 次请求 · 上下文 %s → %s tokens" % (node["title"], format(len(node["request_ids"]), ","), format(tokens["first"], ",") if tokens["first"] is not None else "未知", format(tokens["last"], ",") if tokens["last"] is not None else "未知")
        lines.append(prefix + "├─ " + head)
        for group, title in GROUPS.items():
            ids = node["groups"][group]
            if not ids:
                continue
            count = len(node["request_ids"]) if group == "requests" else len(ids)
            stats = node["group_stats"][group]
            lines.append(prefix + "│  ├─ %s %s · %s 字" % (title, format(count, ","), format(stats["characters"], ",")))
            if group == "requests":
                for rid in node["request_ids"]:
                    req = data["requests"][rid]
                    if req.get("stub"):
                        continue
                    lines.append(prefix + "│  │  ├─ 第 %d 次 · %s tokens · 新加 %d 条%s" % (req["number"], format(req["context_tokens"], ",") if req["context_tokens"] is not None else "未知", len(req["new_message_source_ids"]), " · 上下文清理" if req["cleanup"]["changed"] else ""))
                continue
            if group == "files":
                ids = sorted(ids, key=lambda i: (str(Path(data["items"][i]["path"]).parent), data["items"][i]["path"]))
            last_directory = None
            for iid in ids:
                item = data["items"][iid]
                directory = str(Path(item["path"]).parent) if group == "files" else None
                if directory is not None and directory != last_directory:
                    lines.append(prefix + "│  │  ├─ " + directory + "/")
                    last_directory = directory
                detail = " · %s 字" % format(item["characters"], ",")
                if item.get("reads"):
                    detail = " · 读 %s 次 · " % format(len(item["reads"]), ",") + "；".join("第 %d 次起 %s（%s）" % (r["request"], r["method"], r["coverage"]["label"]) for r in item["reads"])
                elif item.get("writes"):
                    detail = " · " + "；".join("第 %d 次 %s%s" % (w["request"], w["method"], "（仅参数候选）" if w.get("confidence") == "ambiguous_argument" else "") for w in item["writes"])
                elif item.get("kind") == "dispatch" and item["first_request"]:
                    detail += " · 第 %d 次派" % item["first_request"]
                elif item["first_request"]:
                    detail += " · 第 %d 次起" % item["first_request"]
                if item.get("comparison"):
                    detail += " · " + item["comparison"]["label"]
                if item.get("truncation"):
                    detail += " · " + item["truncation"]["label"]
                if item.get("removed_at"):
                    detail += " · 后来被移出上下文"
                label = Path(item["path"]).name if group == "files" else item.get("path", item["label"])
                lines.append(prefix + ("│  │  │  ├─ " if directory else "│  │  ├─ ") + ("★ " if item["focus_ids"] else "") + label + detail)
        for child in children.get(node["id"], []):
            emit(child, prefix + "│  ")

    for node in children.get(None, []):
        emit(node)
    for edge in data["edges"]:
        if edge["kind"] == "file_flow":
            lines.append("└─ 文件流转 %s · 第 %s 次写 → 第 %s 次起读" % (edge["path"], edge["version_request_id"].rsplit("/", 1)[-1], edge["read_request_id"].rsplit("/", 1)[-1]))
    return "\n".join(lines)


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("list", "find", "data", "build"):
        s = sub.add_parser(name)
        s.add_argument("--projects-dir", default="~/.claude/projects")
        if name in ("list", "data", "build"):
            s.add_argument("--since", help="北京时间，日期或 ISO 时间")
            s.add_argument("--until", help="结束边界；日期含当天，时间不含边界")
        if name == "list":
            s.add_argument("--grep")
        if name == "find":
            s.add_argument("--file", required=True)
            s.add_argument("--json", action="store_true", help="包含命令原文，请重定向到私有文件")
        if name in ("data", "build"):
            s.add_argument("--node", action="append")
            s.add_argument("--from-output")
            s.add_argument("--focus", action="append")
            s.add_argument("--range", help="主会话的起-止请求号，含两端")
            s.add_argument("-o", "--output", required=name == 'build')
            s.add_argument("--tree", action="store_true")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "list":
            list_logs(args)
        elif args.command == "find":
            return find_file(args)
        else:
            if not args.output and not args.tree:
                raise ValueError('data 需要 -o 或 --tree')
            if args.range and not __import__("re").fullmatch(r"[1-9]\d*-[1-9]\d*", args.range):
                raise ValueError("--range 格式必须是 起-止")
            data = build(args)
            if args.command == "build":
                from html_page import render_html
                page = render_html(data)
            out = Path(args.output).expanduser() if args.output else None
            if out:
                out.parent.mkdir(parents=True, exist_ok=True)
                # Only the explicitly requested destination is written. Mode
                # 0600 applies on creation; permissions are never broadened.
                fd = os.open(str(out), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    if args.command == "build":
                        f.write(page)
                    else:
                        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
                        f.write("\n")
            if args.tree:
                print(tree(data))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print("trace: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
