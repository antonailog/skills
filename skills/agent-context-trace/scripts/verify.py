"""Privacy-safe integrity checks for trace JSON and source logs."""
import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path

_SCRIPT_DIR = str(Path(__file__).resolve().parent)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from records import Log, blocks, digest


def audit(data):
    sources, images, items, requests = (data[k] for k in ("sources", "images", "items", "requests"))

    def restore(value):
        if isinstance(value, list):
            return [restore(v) for v in value]
        if not isinstance(value, dict):
            return value
        result = {k: restore(v) for k, v in value.items() if k != "data_ref"}
        if "data_ref" in value:
            result["data"] = images[value["data_ref"]]["base64"]
        return result

    def resolve(ref):
        value = sources[ref["source_id"]]
        for part in ref.get("pointer", "").split("/")[1:]:
            part = part.replace("~1", "/").replace("~0", "~")
            value = value[int(part)] if isinstance(value, list) else value[part]
        if "start" in ref:
            assert isinstance(value, str)
            assert 0 <= ref["start"] <= ref["end"] <= len(value)
            return value[ref["start"]:ref["end"]]
        return value

    def walk(value):
        if isinstance(value, list):
            for v in value:
                walk(v)
        elif isinstance(value, dict):
            if "source_id" in value and "pointer" in value:
                resolve(value)
            else:
                for v in value.values():
                    walk(v)

    for key in ("nodes", "items", "requests", "edges", "focus"):
        walk(data[key])
    if data.get('schema_version') == '2.0':
        for key in ('events', 'segments', 'context_compositions', 'file_references', 'files'):
            walk(data[key])
    for h, image in images.items():
        raw = base64.b64decode(image["base64"])
        assert hashlib.sha256(raw).hexdigest() == h
        assert len(raw) == image["bytes"]
    for sid, value in sources.items():
        assert "source:" + digest(restore(value)) == sid
    write_ids, read_ids = set(), set()
    for node in data["nodes"]:
        assert (node.get("verification") or {}).get("missing_messages", 0) == 0
        for group, ids in node["groups"].items():
            assert len(ids) == len(set(ids))
            for iid in ids:
                assert items[iid]["node_id"] == node["id"]
                assert items[iid]["group"] == group
        for rid in node["request_ids"]:
            assert requests[rid]["node_id"] == node["id"]
    for item in items.values():
        for rid in item["request_ids"]:
            assert rid in requests
        for write in item.get("writes", []):
            assert write["id"] not in write_ids
            write_ids.add(write["id"])
            assert write["context_request_id"] in requests
        for read in item.get("reads", []):
            assert read["id"] not in read_ids
            read_ids.add(read["id"])
            assert read["request_id"] in requests
    conflicts = set()
    for req in requests.values():
        if req.get("stub"):
            continue
        own = {x["location"]: x for x in req["ownership"]}
        assert len(own) == len(req["ownership"])
        expected = {}
        shape = resolve(req["shape_ref"])
        expected["system"] = shape["system"]
        expected.update({"tools/%d" % i: tool for i, tool in enumerate(shape.get("tools", []))})
        count = 0
        for mi, (h, sid) in enumerate(zip(req["message_hashes"], req["message_source_ids"])):
            message = sources[sid]
            if digest(restore(message)) != h:
                conflicts.add((req["node_id"], h))
                count += 1
            for bi, block in enumerate(blocks(message["content"])):
                location = "messages/%d/content/%d" % (mi, bi)
                expected[location] = block if isinstance(message["content"], list) else message["content"]
            for key in message.keys() - {"role", "content"}:
                expected["messages/%d/%s" % (mi, key)] = message[key]
        assert count == req["verification"]["hash_mismatches"]
        assert req["verification"].get("missing_messages", 0) == 0
        used = set()
        for location, value in expected.items():
            if location in own:
                ref = own[location]["raw_ref"]
                expected_value = value.get("text") if "start" in ref and isinstance(value, dict) and value.get("type") == "text" else value
                assert resolve(ref) == expected_value, "ownership mismatch at " + location
                used.add(location)
            else:
                slices = sorted((k, v) for k, v in own.items() if k.startswith(location + "/slice/"))
                assert slices, "unowned content location"
                slices.sort(key=lambda x: x[1]["raw_ref"]["start"])
                text = value["text"] if isinstance(value, dict) else value
                assert "".join(resolve(x["raw_ref"]) for _, x in slices) == text
                used.update(k for k, _ in slices)
        assert used == set(own)
        for owner in own.values():
            assert owner["owner_id"] in req["context_item_ids"]
            assert all(i in items for i in owner["related_ids"])
    for edge in data["edges"]:
        if edge["kind"] == "file_flow":
            assert edge["version_write_id"] in write_ids
            assert edge["read_id"] in read_ids
            assert all(w in write_ids for w in edge["write_ids"])
        else:
            assert edge["parent_request_id"] in requests
            assert edge["parent_item_id"] in items
            if edge["child_item_id"]:
                assert edge["child_item_id"] in items
    if data.get('schema_version') == '2.0':
        audit_v2(data, resolve)
    return {"nodes": len(data["nodes"]), "requests": sum(not r.get("stub", False) for r in requests.values()),
            "hash_mismatches": len(conflicts), "missing_messages": 0, "images": len(images), "references_valid": True,
            "context_coverage_exact": True, "unknown_items": sum(i["group"] == "unknown" for i in items.values())}


def audit_v2(data, resolve):
    """Check navigation and accounting without displaying private source text."""
    from chain import CATEGORIES, event_counts
    events, segments = data['events'], data['segments']
    nodes = {n['id']: n for n in data['nodes']}
    for node in nodes.values():
        ids = node['event_ids']
        assert len(ids) == len(set(ids))
        assert all(events[e]['node_id'] == node['id'] and events[e]['kind'] == 'event' for e in ids)
        assert node['overview']['operation_counts'] == event_counts(events[e] for e in ids)
        covered = list(node.get('leading_event_ids', []))
        assert all(events[e]['operation'] == 'user' and not events[e].get('segment_id') for e in covered)
        for sid in node['segment_ids']:
            s = segments[sid]
            assert s['node_id'] == node['id']
            assert s['event_count'] == len(s['event_ids'])
            assert s['operation_counts'] == event_counts(events[e] for e in s['event_ids'])
            covered.extend(s['event_ids'] + s['ending_event_ids'])
            expanded = [child for eid in s['tree_event_ids'] for child in events[eid].get('child_event_ids', [eid])]
            assert expanded == s['event_ids']
            assert all(events[e].get('ends_segment') == s['end_kind'] for e in s['ending_event_ids'])
            assert all(events[e].get('segment_id') == sid for e in s['event_ids'] + s['ending_event_ids'])
            c = data['context_compositions'][s['context_composition_id']]
            assert c['request_id'] == s['context_request_id']
            assert set(c['categories']) == set(CATEGORIES)
            assert c['characters'] == sum(cat['characters'] for cat in c['categories'].values())
            for cat in c['categories'].values():
                assert cat['characters'] == sum(p['characters'] for p in cat['parts'])
                assert all(e in events for e in cat['event_ids'])
                assert all(i in data['items'] for i in cat['item_ids'])
        assert covered == ids
    for e in events.values():
        assert e['request_id'] in data['requests']
        if e['kind'] == 'inputs':
            assert len(e['child_event_ids']) >= 1 and e['event_count'] >= 2
            continue
        if e['kind'] == 'group':
            assert len(e['child_event_ids']) >= 3
            continue
        assert e['operation_label'] == data['operation_labels'][e['operation']]
        assert all(i in data['items'] for i in e['item_ids'])
        assert all(i in data['images'] for i in e['image_ids'])
        if e.get('child_node_id'):
            assert e['child_node_id'] in nodes
        if e.get('content_ref'):
            assert e['visible_characters'] == len(resolve(e['content_ref']))
    for path, f in data['files'].items():
        assert f['path'] == path
        assert len(f['event_ids']) == len(set(f['event_ids']))
        assert all(e in events for e in f['event_ids'])
        for r in f['read_ranges']:
            assert r['event_id'] in f['event_ids']
            assert 1 <= r['start'] <= r['end']
        if f['content_version'] == 'current':
            assert len(resolve(f['content_ref']).encode('utf-8')) <= 1024 * 1024
    for r in data['file_references']:
        assert r.get('kind', 'file') in ('file', 'dir')
        if r.get('kind') == 'dir':
            assert r['path'] not in data['files'] and r['file_id'] is None
        else:
            assert r['path'] in data['files']
            assert r['file_id'] == data['files'][r['path']]['id']
        text = resolve(r['text_ref'])
        assert 0 <= r['start'] < r['end'] <= len(text)
        assert all(o in events or o in data['items'] for o in r['owner_ids'])
    for edge in data['edges']:
        assert edge['source_node_id'] in nodes and edge['target_node_id'] in nodes
        assert edge['source_event_id'] in events
        if edge['kind'] == 'file_flow':
            assert edge['target_event_id'] in events


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--node", action="append", default=[])
    p.add_argument("--data", action="append", default=[])
    args = p.parse_args()
    try:
        for path in args.node:
            log = Log(path)
            result = log.reconstruct()["verification"]
            print(json.dumps({"node": log.path.stem, **result}, ensure_ascii=False))
        for path in args.data:
            result = audit(json.loads(Path(path).read_text(encoding="utf-8")))
            print(json.dumps({"artifact": Path(path).name, **result}, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, AssertionError) as exc:
        print("verify: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
