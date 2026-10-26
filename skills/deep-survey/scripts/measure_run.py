#!/usr/bin/env python3
"""Measure an explicitly scoped research run from existing Codex JSONL records.

No network, pricing assumptions, log discovery or cumulative-snapshot summing.
Pass the root log, root turn ID, explicit child logs and UTC/timezone-aware boundaries.
The final reply is excluded unless its usage record already exists inside the cutoff.
"""
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def instant(s):
    value = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if value.tzinfo is None: raise ValueError("Timestamps must include a timezone")
    return value.astimezone(timezone.utc)


def records(path):
    # A live log may end with an unfinished line; ignore only that last partial line.
    with Path(path).open(encoding="utf-8") as f:
        for number, line in enumerate(f, 1):
            try: yield json.loads(line)
            except json.JSONDecodeError:
                if not line.endswith("\n"): return
                raise ValueError(f"Invalid JSONL at {path}:{number}")


def measure(root_log, child_logs, turn_id, start, end):
    lo, hi = instant(start), instant(end)
    if hi < lo: raise ValueError("end precedes start")
    root_log = Path(root_log)
    first = next(records(root_log))
    if first.get("type") != "session_meta": raise ValueError("Missing root session metadata")
    root_id = first["payload"]["id"]
    paths = [root_log] + [Path(p) for p in child_logs]
    if len({p.resolve() for p in paths}) != len(paths): raise ValueError("Duplicate log path")
    seen = {}; roles = []; warnings = []; duplicate_count = 0
    fields = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens", "reasoning_output_tokens", "total_tokens")
    for index, path in enumerate(paths):
        rows = records(path); meta = next(rows)
        if meta.get("type") != "session_meta": raise ValueError(f"Missing session metadata: {path}")
        session = meta["payload"]; sid = session["id"]
        source = session.get("source", {})
        spawn = source.get("subagent", {}).get("thread_spawn", {}) if isinstance(source, dict) else {}
        if index and spawn.get("parent_thread_id") != root_id:
            raise ValueError(f"Child {sid} is not a direct child of {root_id}")
        counts = Counter(); known = {k: True for k in fields}; models = set(); tools = Counter(); n = 0; first_at = last_at = None
        for row in rows:
            timestamp = row.get("timestamp")
            if not timestamp or not lo <= instant(timestamp) <= hi: continue
            q = row.get("payload", {})
            if row["type"] == "turn_context": models.add((q.get("model"), q.get("effort")))
            if row["type"] == "response_item" and q.get("type") in ("function_call", "custom_tool_call"):
                tools[q.get("name", "unknown")] += 1
            if row["type"] != "token_usage_record" or q.get("thread_id") != sid: continue
            if not index and q.get("turn_id") != turn_id: continue
            rid = q.get("response_id")
            if not rid: raise ValueError("Usage record without response_id")
            usage = q.get("usage", {})
            if rid in seen:
                if seen[rid] != usage: raise ValueError(f"Conflicting usage for {rid}")
                duplicate_count += 1; continue
            seen[rid] = usage; n += 1; first_at = first_at or timestamp; last_at = timestamp
            for k in fields:
                v = usage.get(k)
                if v is None: known[k] = False
                elif not isinstance(v, int) or v < 0: raise ValueError(f"Invalid {k} for {rid}")
                else: counts[k] += v
        if not n: warnings.append(f"No scoped usage records for {sid}")
        u = {k: counts[k] if known[k] and n else None for k in fields}
        u["uncached_input_tokens"] = u["input_tokens"]-u["cached_input_tokens"] if u["input_tokens"] is not None and u["cached_input_tokens"] is not None else None
        if u["uncached_input_tokens"] is not None and u["uncached_input_tokens"] < 0: raise ValueError("Cached input exceeds input")
        roles.append({"thread_id": sid, "role": session.get("agent_path", "/root" if not index else "child"), "log": str(path.resolve()),
                      "model_responses": n, "usage": u, "models": sorted(models, key=str), "tool_calls_in_time_window": dict(tools),
                      "first_usage_at": first_at, "last_usage_at": last_at})
    aggregate = {}
    for k in (*fields, "uncached_input_tokens"):
        aggregate[k] = sum(r["usage"][k] for r in roles) if all(r["usage"][k] is not None for r in roles) else None
    return {"schema_version": 1, "root_thread_id": root_id, "root_turn_id": turn_id, "start": start, "cutoff": end,
            "elapsed_seconds": (hi-lo).total_seconds(), "model_responses": sum(r["model_responses"] for r in roles), "aggregate": aggregate,
            "roles": roles, "duplicate_records_ignored": duplicate_count, "warnings": warnings,
            "scope_notes": ["Explicit logs only; platform guardian and unlisted tasks are excluded.",
                            "Per-response usage only; cumulative token snapshots and forwarded child records are ignored.",
                            "Cached input is part of input; reasoning output is part of output. Do not add either twice.",
                            "Missing measurements are null, not zero. Token totals are not billing amounts.",
                            "Only already-recorded responses inside the cutoff are measured; later evaluation/final replies are excluded.",
                            "Tool counts use the time window; usage is additionally restricted to the root turn ID."]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root-log", type=Path, required=True); ap.add_argument("--child-log", type=Path, action="append", default=[])
    ap.add_argument("--turn-id", required=True); ap.add_argument("--start", required=True); ap.add_argument("--end", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    try: result = measure(a.root_log, a.child_log, a.turn_id, a.start, a.end)
    except (ValueError, KeyError, OSError, StopIteration) as e: ap.error(str(e))
    a.out.parent.mkdir(parents=True, exist_ok=True); a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: result[k] for k in ("elapsed_seconds", "model_responses", "aggregate", "warnings")}, ensure_ascii=False))


if __name__ == '__main__':
    main()
