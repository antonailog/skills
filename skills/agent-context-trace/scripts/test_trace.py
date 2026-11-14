"""Synthetic regression tests. No private session excerpts or local paths."""
import argparse
import base64
import contextlib
import io
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from records import Log, digest, human_message
from shell import analyze, inline_paths, segments
from provenance import Catalog, comparison, visible_text
from model import Document, NodeBuilder
from trace import build, display_range, display_time, finalize, tree
from verify import audit


def scratch_directory():
    return tempfile.TemporaryDirectory(prefix="trace-test-", dir=os.path.realpath(tempfile.gettempdir()))


class ShellTests(unittest.TestCase):
    def setUp(self):
        self.tmp = scratch_directory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        for name in ("a.md", "b.md", "image.png", "run.py"):
            (self.root / name).write_text("alpha\nbeta\n")

    def run_shell(self, command):
        return analyze(command, str(self.root))

    def test_option_values_are_not_files(self):
        for command in ("head -c 6000 a.md", "head -n 20 a.md", "grep -A3 'beta' a.md", "grep -A 3 -e beta a.md", "sed -n '1,40p' a.md", "awk -F : '{print $1}' a.md", "nl -w 4 -ba a.md"):
            with self.subTest(command=command):
                rows = self.run_shell(command)["reads"]
                self.assertEqual([r["path"] for r in rows], [str(self.root / "a.md")])

    def test_separators_and_quoted_pattern(self):
        rows = self.run_shell("grep 'x|y;z' a.md | head -n 3 && cat b.md\nsed -n '1,2p' a.md || tail -n 2 b.md")["reads"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(rows[0]["coverage"]["selectors"]), 3)

    def test_heredoc_body_is_not_shell(self):
        result = self.run_shell("cat > generated.py <<'END'\ncat fake.md\nopen('also-fake.md', 'w')\nEND\ncat a.md")
        self.assertEqual([Path(r["path"]).name for r in result["reads"]], ["a.md"])
        self.assertEqual([Path(r["path"]).name for r in result["writes"]], ["generated.py"])
        self.assertEqual(result['writes'][0]['literal_content'], "cat fake.md\nopen('also-fake.md', 'w')\n")
        self.assertNotIn('literal_content', self.run_shell('cat > a.md <<EOF\n$UNKNOWN\nEOF')['writes'][0])

    def test_static_assignments_cd_and_pwd(self):
        result = self.run_shell("W='" + str(self.root) + "'; cat \"$W/a.md\"; cd \"$W\" && cat \"${PWD}/b.md\"")
        self.assertEqual({Path(r["path"]).name for r in result["reads"]}, {"a.md", "b.md"})
        self.assertEqual(self.run_shell('cat "$UNRESOLVED/a.md"')["reads"], [])

    def test_glob_and_two_reads_one_call(self):
        rows = self.run_shell("cat *.md; sed -n '1,2p' a.md; sed -n '4,5p' a.md")["reads"]
        self.assertEqual(len(rows), 2)

    def test_script_output_with_trailing_asset(self):
        result = self.run_shell("python3 -I run.py a.md image.png b.md image.png")
        output = result["writes"][0]
        self.assertEqual(Path(output["path"]).name, "b.md")
        self.assertIn(str(self.root / "a.md"), output["inputs"])
        self.assertEqual(result["executed"], [str(self.root / "run.py")])

    def test_numeric_script_argument_is_not_a_file(self):
        (self.root / "in.mp4").write_text("x")
        result = self.run_shell("bash make.sh in.mp4 out/clip.gif 960 0 15.5")
        self.assertEqual([Path(w["path"]).name for w in result["writes"]], ["clip.gif"])

    def test_inline_writes_do_not_include_read_inputs(self):
        body = "from pathlib import Path\ns=Path('a.md').read_text()\np=Path('b.md')\np.write_text(s)"
        self.assertEqual(inline_paths(body, str(self.root)), [str(self.root / "b.md")])
        command = "python3 - <<'PY'\n" + body + "\nPY"
        self.assertEqual([r["path"] for r in self.run_shell(command)["writes"]], [str(self.root / "b.md")])

    def test_heredoc_paths_use_each_header_cwd(self):
        command = ("cd recording; python3 - <<'PY'\n"
                   "p='worker.js'\nopen(p, 'w').write('changed')\nPY\n"
                   "node worker.js && cd frames && python3 - <<'NEXT'\n"
                   "open('details.txt', 'w').write('details')\nNEXT\ncd ..")
        outputs = {r["path"] for r in self.run_shell(command)["writes"]}
        self.assertEqual(outputs, {str(self.root / "recording/worker.js"),
                                   str(self.root / "recording/frames/details.txt")})

    def test_redirects_and_tee(self):
        result = self.run_shell("echo hello > a.md; echo next >> b.md; echo copy | tee -a a.md")
        self.assertEqual({Path(r["path"]).name for r in result["writes"]}, {"a.md", "b.md"})

    def test_sed_in_place_is_one_write_not_a_script_path_read(self):
        for command in ("sed -i '' 's/alpha/beta/' a.md", "sed -i 's/alpha/beta/' a.md", "sed --in-place 's/alpha/beta/' a.md"):
            result = self.run_shell(command)
            self.assertEqual(result['reads'], [])
            self.assertEqual([w['path'] for w in result['writes']], [str(self.root / 'a.md')])

    def test_explicit_output_and_ambiguous_reference_arguments(self):
        other = self.root / "references"
        other.mkdir()
        reference = other / "source.md"
        reference.write_text("reference")
        row = self.run_shell("python3 run.py a.md references/source.md")["writes"][0]
        self.assertEqual(row["confidence"], "ambiguous_argument")
        row = self.run_shell("python3 run.py a.md --output=references/source.md image.png")["writes"][0]
        self.assertEqual(row["path"], str(reference))
        self.assertEqual(row["confidence"], "explicit")


class ComparisonTests(unittest.TestCase):
    def test_read_numbers_and_truncation(self):
        text, cut = visible_text("    1→alpha\n    2→beta\n<system-reminder>notice</system-reminder>", "Read")
        self.assertEqual(text, "alpha\nbeta")
        text, cut = visible_text("<persisted-output>\nOutput too large (9KB)\nPreview (first 2KB):\nalpha\n...\n</persisted-output>")
        self.assertEqual(cut["preview"], "2KB")
        self.assertIn("alpha", text)

    def test_comparison(self):
        with scratch_directory() as tmp:
            p = Path(tmp) / "input.md"
            p.write_text("alpha\nbeta\ngamma\n")
            self.assertEqual(comparison(str(p), "alpha\nbeta\ngamma", True)["status"], "same")
            self.assertEqual(comparison(str(p), "beta", False)["status"], "same")
            self.assertEqual(comparison(str(p), "unknown", False)["status"], "different")
            self.assertEqual(comparison(str(p))["status"], "unavailable")
            image = Path(tmp) / "image.png"
            image.write_bytes(b"synthetic original image")
            read_at = "2026-01-02T00:00:00Z"
            read_seconds = datetime.fromisoformat(read_at.replace("Z", "+00:00")).timestamp()
            os.utime(image, (read_seconds, read_seconds))
            scaled = [hashlib.sha256(b"synthetic scaled image").hexdigest()]
            result = comparison(str(image), image_hashes=scaled, read_timestamp=read_at)
            self.assertEqual(result["status"], "same")
            self.assertEqual(result["basis"], "图片缩放过，按修改时间判断")
            os.utime(image, (read_seconds + 1, read_seconds + 1))
            self.assertEqual(comparison(str(image), image_hashes=scaled, read_timestamp=read_at)["status"], "different")
            original = [hashlib.sha256(image.read_bytes()).hexdigest()]
            self.assertEqual(comparison(str(image), image_hashes=original, read_timestamp=read_at)["status"], "same")


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = scratch_directory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.log_path = self.root / "session.jsonl"

    def write(self, entries):
        self.log_path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")

    def fixture(self):
        shape = {"system": [{"type": "text", "text": "system"}], "tools": []}
        prompt = {"role": "user", "content": "Please inspect the input."}
        assistant = {"role": "assistant", "content": [
            {"type": "thinking", "thinking": "consider", "signature": "sig"},
            {"type": "tool_use", "id": "call", "name": "Read", "input": {"file_path": str(self.root / "input.md")}, "caller": {"type": "direct"}}]}
        result = {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "call", "content": "1→alpha"}]}
        entries = [
            {"type": "user", "cwd": str(self.root), "timestamp": "2026-01-01T00:00:00Z", "message": prompt},
            {"type": "api-request-shape", "shapeHash": "shape", "shape": shape},
            {"type": "api-request-blob", "hash": digest(prompt), "message": prompt},
            {"type": "api-request", "id": "r1", "timestamp": "2026-01-01T00:00:01Z", "shapeHash": "shape", "keep": 0, "tail": [digest(prompt)]},
            {"type": "assistant", "requestRef": "r1", "apiBlockIndex": 1, "timestamp": "2026-01-01T00:00:02Z", "wireToolInputs": {"call": assistant["content"][1]["input"]}, "message": {"content": [dict(assistant["content"][1], input={})], "usage": {"input_tokens": 3}}},
            {"type": "assistant", "requestRef": "r1", "apiBlockIndex": 0, "timestamp": "2026-01-01T00:00:03Z", "message": {"content": assistant["content"][:1], "usage": {"input_tokens": 3, "cache_read_input_tokens": 4, "cache_creation_input_tokens": 5}}},
            {"type": "user", "timestamp": "2026-01-01T00:00:04Z", "message": result},
            {"type": "api-request", "id": "r2", "timestamp": "2026-01-01T00:00:05Z", "shapeHash": "shape", "keep": 1, "tail": [digest(assistant), digest(result)]},
            {"type": "api-request", "id": "r3", "timestamp": "2026-01-01T00:00:06Z", "shapeHash": "shape", "keep": 1, "tail": []},
        ]
        return entries, assistant, result

    def test_wire_input_caller_order_keep_and_usage(self):
        entries, assistant, result = self.fixture()
        self.write(entries)
        log = Log(self.log_path)
        r = log.reconstruct()
        self.assertEqual(r["verification"]["hash_mismatches"], 0)
        self.assertEqual(r["messages"][digest(assistant)], assistant)
        self.assertEqual(len(r["requests"][2]["removed_hashes"]), 2)
        doc = Document({}, {})
        node = doc.node(log, "full")
        NodeBuilder(doc, log, node, r).build()
        self.assertEqual(node["context_tokens"]["first"], 12)
        file = doc.data["items"][node["groups"]["files"][0]]
        self.assertEqual(file["first_request"], 2)
        self.assertTrue(file["reads"][0]["removed_at"])

    def test_missing_hash_fails_closed(self):
        entries, _, _ = self.fixture()
        entries[-1]["tail"] = ["f" * 64]
        self.write(entries)
        with self.assertRaisesRegex(ValueError, "无法按哈希"):
            Log(self.log_path).reconstruct()
        for script, arguments in (("trace.py", ["data", "--node", str(self.log_path), "-o", str(self.root / "missing.json")]),
                                  ("verify.py", ["--node", str(self.log_path)])):
            result = subprocess.run([sys.executable, "-I", str(Path(__file__).with_name(script))] + arguments, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stderr)

    def test_meta_list_is_merged_with_tool_result(self):
        entries, assistant, result = self.fixture()
        note = {"type": "text", "text": "skill instructions"}
        combined = {"role": "user", "content": result["content"] + [note]}
        entries.insert(7, {"type": "user", "isMeta": True, "message": {"role": "user", "content": [note]}})
        entries[8]["tail"][-1] = digest(combined)
        self.write(entries)
        self.assertEqual(Log(self.log_path).reconstruct()["messages"][digest(combined)], combined)

    def test_conflicting_stored_blob_is_reported_not_rewritten(self):
        entries, _, _ = self.fixture()
        entries[2]["message"] = {"role": "user", "content": "changed stored blob"}
        # Remove the conversation copy which could independently recover it.
        entries = entries[1:4]
        self.write(entries)
        log = Log(self.log_path)
        r = log.reconstruct()
        self.assertEqual(r["verification"]["hash_mismatches"], 1)
        self.assertEqual(r["verification"]["missing_messages"], 0)
        self.assertEqual(next(iter(r["messages"].values()))["content"], "changed stored blob")
        output = self.root / "conflict.json"
        result = subprocess.run([sys.executable, "-I", str(Path(__file__).with_name("trace.py")), "data", "--node", str(self.log_path), "-o", str(output), "--tree"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("还原校验", result.stdout)
        result = subprocess.run([sys.executable, "-I", str(Path(__file__).with_name("verify.py")), "--data", str(output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_old_record_is_unsupported(self):
        self.write([{"type": "user", "message": {"role": "user", "content": "hello"}}])
        with self.assertRaisesRegex(ValueError, "不支持"):
            Log(self.log_path).reconstruct()

    def test_human_filter(self):
        self.assertFalse(human_message({"type": "user", "isMeta": True, "message": {"content": "hello"}}))
        self.assertFalse(human_message({"type": "user", "message": {"content": "<system-reminder>notice</system-reminder>"}}))
        self.assertTrue(human_message({"type": "user", "message": {"content": "hello <system-reminder>notice</system-reminder>"}}))

    def test_image_dedup_and_rehydration(self):
        doc = Document({}, {})
        image = {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(b"synthetic-image").decode()}}
        doc.source([image, image])
        self.assertEqual(len(doc.data["images"]), 1)

    def test_merged_attachments_and_tool_addition_ownership(self):
        entries, _, _ = self.fixture()
        tool = {"name": "Example", "description": "example", "input_schema": {"type": "object"}}
        rendered = [
            {"type": "attachment", "attachment": {"type": "environment"}, "renderedRole": "system", "rendered": [{"content": "<system-reminder>\nenvironment\n</system-reminder>"}]},
            {"type": "attachment", "attachment": {"type": "deferred_tools_delta", "surfacedDefinitions": [{"definition": tool}]}, "renderedRole": "system", "rendered": [{"content": "<system-reminder>\nnew tools\n</system-reminder>"}]},
        ]
        message = {"role": "system", "content": [{"type": "text", "text": "environment\n\nnew tools"}, {"type": "tool_addition", "tool": tool}]}
        entries = entries[:3] + rendered + [{"type": "api-request-blob", "hash": digest(message), "message": message}, dict(entries[3], tail=[digest(message)])]
        self.write(entries)
        log = Log(self.log_path)
        doc = Document({}, {})
        node = doc.node(log, "full")
        NodeBuilder(doc, log, node, log.reconstruct()).build()
        self.assertEqual(len(node["groups"]["automatic"]), 2)
        self.assertEqual(node["groups"]["unknown"], [])
        request = doc.data["requests"][node["request_ids"][0]]
        slices = [o["raw_ref"] for o in request["ownership"] if o["location"].startswith("messages/0/content/0")]
        self.assertEqual("".join(doc.resolve(x) for x in slices), message["content"][0]["text"])
        self.assertTrue(audit(doc.data)["context_coverage_exact"])


class ScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = scratch_directory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.agents = self.project / "session" / "subagents"
        self.agents.mkdir(parents=True)
        self.input = self.root / "notes.md"
        self.input.write_text("Synthetic reference text.\n")
        self.output = self.root / "result.md"
        self.output.write_text("Synthetic article.\n")
        self.shape = {"system": [{"type": "text", "text": "system"}], "tools": []}

    def log(self, path, prompt, turns, start_minute=0, meta=None):
        message = {"role": "user", "content": prompt}
        entries = [{"type": "api-request-shape", "shapeHash": "shape", "shape": self.shape},
                   {"type": "user", "cwd": str(self.root), "message": message, "timestamp": "2026-01-02T00:00:00Z"},
                   {"type": "api-request-blob", "hash": digest(message), "message": message}]
        messages, previous = [message], []
        for i, (reply_blocks, result_blocks) in enumerate(turns, 1):
            minute = start_minute + i
            ts = "2026-01-02T00:%02d:00Z" % minute
            rid = "r%d" % i
            tail = messages[len(previous):]
            for m in tail:
                entries.append({"type": "api-request-blob", "hash": digest(m), "message": m})
            entries.append({"type": "api-request", "id": rid, "timestamp": ts, "shapeHash": "shape", "keep": len(previous), "tail": [digest(m) for m in tail]})
            previous = list(messages)
            reply = {"role": "assistant", "content": reply_blocks}
            entries.append({"type": "assistant", "requestRef": rid, "timestamp": ts, "message": dict(reply, usage={"input_tokens": 100 * i})})
            messages.append(reply)
            if result_blocks:
                result = {"role": "user", "content": result_blocks}
                entries.append({"type": "user", "timestamp": "2026-01-02T00:%02d:01Z" % minute, "message": result})
                messages.append(result)
        path.write_text("\n".join(json.dumps(x) for x in entries))
        if meta:
            path.with_suffix(".meta.json").write_text(json.dumps(meta))

    def family(self):
        self.log(self.project / "session.jsonl", "Please prepare an article.", [([
            {"type": "tool_use", "id": "spawn-p", "name": "Agent", "input": {"description": "Research", "prompt": "Prepare notes."}},
            {"type": "tool_use", "id": "spawn-w", "name": "Agent", "input": {"description": "Writer", "prompt": "Write an article."}},
        ], [])])
        self.log(self.agents / "agent-producer.jsonl", "Prepare notes.", [([
            {"type": "tool_use", "id": "write-notes", "name": "Write", "input": {"file_path": str(self.input), "content": self.input.read_text()}},
        ], [{"type": "tool_result", "tool_use_id": "write-notes", "content": "Written."}]),
            ([{"type": "text", "text": "Notes ready."}], [])], 2, {"toolUseId": "spawn-p", "description": "Research"})
        self.log(self.agents / "agent-writer.jsonl", "Write an article.", [([
            {"type": "tool_use", "id": "read-notes", "name": "Read", "input": {"file_path": str(self.input)}},
        ], [{"type": "tool_result", "tool_use_id": "read-notes", "content": "1→" + self.input.read_text()}]),
            ([{"type": "tool_use", "id": "write-article", "name": "Write", "input": {"file_path": str(self.output), "content": self.output.read_text()}}], [])], 5, {"toolUseId": "spawn-w", "description": "Writer"})

    def args(self, **kw):
        values = dict(projects_dir=str(self.root), node=None, from_output=None, focus=[], since=None, until=None, range=None)
        values.update(kw)
        return argparse.Namespace(**values)

    def test_file_predecessor_and_dispatch_expansion(self):
        self.family()
        data = build(self.args(from_output=str(self.output)))
        self.assertEqual(len(data["nodes"]), 3)
        edge = next(e for e in data["edges"] if e["kind"] == "file_flow")
        self.assertTrue(edge["version_request_id"].endswith("/1"))
        self.assertTrue(edge["read_request_id"].endswith("/2"))
        self.assertTrue(audit(data)["references_valid"])
        self.assertIn("调用 Research", tree(data))
        self.assertEqual(display_time("2026-01-01T23:00:00Z"), "01-02 07:00")
        self.assertEqual(display_range("2026-01-01T23:00:00Z", "2026-01-01T23:10:00Z"), "01-02 07:00–07:10")
        self.assertEqual(display_range("2026-01-01T15:59:00Z", "2026-01-01T16:01:00Z"), "01-01 23:59–01-02 00:01")

    def test_focus_only_and_date_filter(self):
        self.family()
        data = build(self.args(focus=[str(self.root / "unread.md"), str(self.input)], since="2026-01-02", until="2026-01-02"))
        self.assertEqual(len(data["nodes"]), 2)
        loaded = next(f for f in data["focus"] if f["status"] == "读全了")
        self.assertEqual(loaded["read_count"], 1)
        # Focus statistics moved into each agent overview in v2.
        coverage = [f for n in data['nodes'] for f in n['overview']['focus_coverage']]
        self.assertTrue(any(f['appeared'] and f['path'] == str(self.input) for f in coverage))
        self.assertTrue(all(not f['appeared'] for f in coverage if f['path'].endswith('/unread.md')))
        self.assertTrue(audit(data)["context_coverage_exact"])

    def test_failed_write_does_not_become_a_producer(self):
        self.family()
        path = self.agents / "agent-producer.jsonl"
        entries = [json.loads(line) for line in path.read_text().splitlines()]
        for entry in entries:
            if entry["type"] == "user" and isinstance(entry["message"]["content"], list):
                entry["message"]["content"][0]["is_error"] = True
        path.write_text("\n".join(json.dumps(x) for x in entries))
        data = build(self.args(from_output=str(self.output)))
        self.assertEqual(len(data["nodes"]), 2)
        self.assertFalse(any(e["kind"] == "file_flow" for e in data["edges"]))

    def test_main_events_before_and_between_dispatches(self):
        self.family()
        self.log(self.project / 'session.jsonl', 'Please prepare an article.', [
            ([{'type': 'tool_use', 'id': 'list', 'name': 'Bash', 'input': {'command': 'ls'}}],
             [{'type': 'tool_result', 'tool_use_id': 'list', 'content': 'notes.md'}]),
            ([{'type': 'tool_use', 'id': 'spawn-p', 'name': 'Agent', 'input': {'prompt': 'Prepare notes.', 'description': 'Research'}}], []),
            ([{'type': 'tool_use', 'id': 'inspect', 'name': 'Read', 'input': {'file_path': str(self.input)}}],
             [{'type': 'tool_result', 'tool_use_id': 'inspect', 'content': '1→' + self.input.read_text()}]),
            ([{'type': 'tool_use', 'id': 'spawn-w', 'name': 'Agent', 'input': {'prompt': 'Write an article.', 'description': 'Writer'}}], [])])
        data = build(self.args(from_output=str(self.output)))
        main = next(n for n in data['nodes'] if not n['agent_id'])
        self.assertEqual([data['events'][row['id']]['operation'] for row in main['timeline']], ['user', 'list', 'spawn', 'read', 'spawn'])
        self.assertEqual(main['range'], {'start': 1, 'end': 4})
        self.assertTrue(all(data['events'][row['id']]['child_node_id'] for row in main['timeline'] if data['events'][row['id']]['operation'] == 'spawn'))
        self.assertTrue(audit(data)['context_coverage_exact'])

    def bash_trace(self, command, output, is_error=False, focus=None):
        path = self.project / 'bash-events.jsonl'
        self.log(path, 'Inspect synthetic files.', [
            ([{'type': 'tool_use', 'id': 'mixed', 'name': 'Bash', 'input': {'command': command}}],
             [{'type': 'tool_result', 'tool_use_id': 'mixed', 'content': output, 'is_error': is_error}]),
            ([{'type': 'text', 'text': 'Done.'}], [])])
        data = build(self.args(node=[str(path)], focus=focus or []))
        node = data['nodes'][0]
        return data, [data['events'][eid] for eid in node['event_ids'] if data['events'][eid].get('tool_use_id') == 'mixed']

    def test_model_text_is_an_output_and_empty_thinking_is_hidden(self):
        path = self.project / 'replies.jsonl'
        self.log(path, 'Write it.', [
            ([{'type': 'thinking', 'thinking': '', 'signature': 'x'},
              {'type': 'text', 'text': 'Reading the notes first.'},
              {'type': 'tool_use', 'id': 'look', 'name': 'Read', 'input': {'file_path': str(self.root / 'notes.md')}}],
             [{'type': 'tool_result', 'tool_use_id': 'look', 'content': 'notes'}]),
            ([{'type': 'tool_use', 'id': 'write', 'name': 'Write', 'input': {'file_path': str(self.output), 'content': 'draft'}}], [])])
        (self.root / 'notes.md').write_text('notes')
        data = build(self.args(node=[str(path)]))
        node = data['nodes'][0]
        events = [data['events'][eid] for eid in node['event_ids']]
        self.assertEqual([e['operation'] for e in events if e['operation'] in ('reply', 'think')], ['reply'])
        reply = next(e for e in events if e['operation'] == 'reply')
        self.assertTrue(reply['is_output'])
        self.assertEqual(reply['display_name'], 'Reading the notes first.')
        rows = [data['events'][eid] for eid in node['trace_rows']]
        self.assertEqual([r['operation'] for r in rows], ['reply', 'read', 'write'])
        self.assertEqual([r['is_output'] for r in rows], [True, False, True])
        self.assertTrue(audit(data)['references_valid'])

    def test_identical_copy_of_focus_file_is_not_a_second_read(self):
        focus_dir = self.root / 'focus'; focus_dir.mkdir()
        copy_dir = self.root / 'snapshot'; copy_dir.mkdir()
        text = '\n'.join('rule line number %d with enough text' % i for i in range(8))
        (focus_dir / 'SKILL.md').write_text(text); (copy_dir / 'SKILL.md').write_text(text)
        path = self.project / 'copy.jsonl'
        self.log(path, 'Use the snapshot.', [
            ([{'type': 'tool_use', 'id': 'r', 'name': 'Read', 'input': {'file_path': str(copy_dir / 'SKILL.md')}}],
             [{'type': 'tool_result', 'tool_use_id': 'r', 'content': text}]),
            ([{'type': 'tool_use', 'id': 'w', 'name': 'Write', 'input': {'file_path': str(self.output), 'content': 'x'}}], [])])
        data = build(self.args(node=[str(path)], focus=[str(focus_dir)]))
        reads = [e['path'] for e in data['events'].values() if e.get('kind') == 'event' and e['operation'] == 'read']
        self.assertEqual(reads, [str(copy_dir / 'SKILL.md')])

    def test_pwd_variable_resolves_script_output_path(self):
        command = 'cd /tmp/work; W="$(pwd)"; python3 /tmp/tool/embed.py "$W/draft.md" "$W/img" "$W/out.md"'
        writes = [w['path'] for w in analyze(command, '/tmp')['writes']]
        self.assertTrue(any(Path(p).name == 'out.md' and '/work/' in p for p in writes), writes)

    def test_file_descriptor_redirect_is_not_a_file_argument(self):
        command = 'cd /tmp; ls a b 2>/dev/null; echo ----; cat 宣传/说明.md 2>/dev/null | head -60; cat c.md 2>&1'
        reads = [Path(r['path']).name for r in analyze(command, '/tmp')['reads']]
        self.assertEqual(reads, ['说明.md', 'c.md'])
        self.assertEqual(segments('cat x.md 2>/dev/null')[0][0], ['cat', 'x.md', '>', '/dev/null'])

    def test_main_writer_has_initial_context_segments_and_image_groups(self):
        path = self.project / 'main-writer.jsonl'
        image = {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png',
                                           'data': base64.b64encode(b'synthetic image').decode()}}
        self.log(path, 'Write without delegating.', [
            ([{'type': 'tool_use', 'id': 'pictures', 'name': 'Read', 'input': {'file_path': str(self.root / 'image.png')}}],
             [{'type': 'tool_result', 'tool_use_id': 'pictures', 'content': [image, image, image]}]),
            ([{'type': 'tool_use', 'id': 'write', 'name': 'Write', 'input': {'file_path': str(self.output), 'content': 'draft'}}], []),
            ([{'type': 'tool_use', 'id': 'edit', 'name': 'Edit', 'input': {'file_path': str(self.output), 'old_string': 'draft', 'new_string': 'final'}}], [])])
        data = build(self.args(node=[str(path)]))
        node = data['nodes'][0]
        self.assertEqual(node['timeline_mode'], 'segments')
        self.assertEqual([data['events'][eid]['operation'] for eid in node['leading_event_ids']], ['user'])
        self.assertEqual([s['event_count'] for s in data['segments'].values()], [3])
        segment = data['segments'][node['segment_ids'][0]]
        self.assertEqual(segment['ending_request_range'], [2, 3])
        self.assertEqual(data['events'][segment['tree_event_ids'][0]]['kind'], 'group')
        self.assertNotIn('task', node['initial_context']['categories'])
        self.assertTrue(all(entry['available_in_first_request'] for cat in node['initial_context']['categories'].values() for entry in cat['entries']))
        self.assertLess(tree(data).index('上下文'), tree(data).index('用户消息'))
        rendered = tree(data)
        # Same structure as the page: 主 Agent → 上下文 → 段「N 次操作 → 写入 X」→ 每次操作，行首是第几轮；段里先输入后写入。
        self.assertLess(rendered.index('主 Agent'), rendered.index('上下文'))
        lines = rendered.splitlines()
        header = next(i for i, line in enumerate(lines) if '次操作 → 写入 result.md' in line)
        read = next(i for i, line in enumerate(lines) if line.strip().startswith('第 2 轮  读取 image.png'))
        write = next(i for i, line in enumerate(lines) if line.strip().startswith('第 2 轮  写入 result.md'))
        edit = next(i for i, line in enumerate(lines) if line.strip().startswith('第 3 轮  编辑 result.md'))
        self.assertLess(header, read); self.assertLess(read, write); self.assertLess(write, edit)
        self.assertGreater(len(lines[read]) - len(lines[read].lstrip()), len(lines[header]) - len(lines[header].lstrip()))
        self.assertTrue(audit(data)['context_coverage_exact'])
        mid_task = build(self.args(node=[str(path)], range='3-3'))
        self.assertIn('history', mid_task['nodes'][0]['initial_context']['categories'])
        history_entries = mid_task['nodes'][0]['initial_context']['categories']['history']['entries']
        self.assertTrue(all(ref['source_id'] in mid_task['sources'] for entry in history_entries for ref in entry['content_refs']))
        # A narrowed main-agent range must retain earlier text and images by
        # reference without rehashing already-encoded image placeholders.
        entries = [json.loads(line) for line in path.read_text().splitlines()]
        start = next(i for i, entry in enumerate(entries) if entry.get('type') == 'api-request' and entry.get('id') == 'r3')
        message = {'role': 'user', 'content': 'Now revise the draft.'}
        entries[start]['tail'].append(digest(message))
        entries[start:start] = [{'type': 'user', 'timestamp': '2026-01-02T00:02:59Z', 'message': message},
                               {'type': 'api-request-blob', 'hash': digest(message), 'message': message}]
        path.write_text('\n'.join(json.dumps(entry) for entry in entries))
        narrowed = build(self.args(node=[str(path)], range='3-3'))
        history = narrowed['nodes'][0]['initial_context']['categories']['history']
        self.assertTrue(history['entries'][0]['content_refs'])
        self.assertTrue(audit(narrowed)['references_valid'])

    def test_document_write_by_command_segments_but_code_write_does_not(self):
        # 11-04 用户：用命令写的文档也切段；写代码文件不切段
        for name in ('worker.js', 'page.html'):
            data, events = self.bash_trace("cat > %s <<'EOF'\nconsole.log(1)\nEOF" % name, 'Written.')
            self.assertEqual(data['nodes'][0]['timeline_mode'], 'events')
            self.assertEqual([(e['operation'], e['ends_segment'], e['is_code']) for e in events], [('write', None, True)])
        data, events = self.bash_trace("cat > result.md <<'EOF'\nfinal\nEOF", 'Written.')
        self.assertEqual(data['nodes'][0]['timeline_mode'], 'segments')
        self.assertEqual([(e['operation'], e['ends_segment'], e['is_code']) for e in events], [('write', 'write', False)])
        data = build(self.args(from_output=str(self.output)))
        self.assertEqual(data['nodes'][0]['timeline_mode'], 'segments')
        self.assertEqual(data['segments'][data['nodes'][0]['segment_ids'][0]]['end_kind'], 'write')

    def test_execution_counts_only_result_not_assigned_to_file_reads(self):
        for command, output, remaining in [
            ('node worker.js; cat notes.md', 'whole shared output', 0),
            ("node worker.js; echo '---'; cat notes.md", 'done\n---\nnotes\n', len('done\n---\n')),
            ('node worker.js; cat notes.md result.md', 'shared by two files', 0),
        ]:
            with self.subTest(command=command):
                data, events = self.bash_trace(command, output)
                execution = next(e for e in events if e['operation'] == 'exec')
                self.assertEqual(execution['characters'], remaining)
                self.assertEqual(data['sources'][execution['content_ref']['source_id']], output)
                self.assertTrue(audit(data)['references_valid'])

    def test_bash_edit_is_separate_from_read_and_owns_its_focus(self):
        command = "python3 - <<'PY'\nfrom pathlib import Path\np=Path('result.md')\np.write_text(p.read_text().replace('old','new'))\nPY\ncat notes.md"
        data, events = self.bash_trace(command, self.input.read_text(), focus=[str(self.output)])
        self.assertEqual([(e['operation'], e['request_number']) for e in events], [('edit', 1), ('read', 2)])
        self.assertEqual([e['path'] for e in events], [str(self.output), str(self.input)])
        self.assertEqual([e['is_focus'] for e in events], [True, False])
        self.assertEqual([e['ends_segment'] for e in events], ['write', None])
        self.assertEqual(events[1]['written_files'], [])
        self.assertTrue(audit(data)['references_valid'])

    def test_bash_write_read_and_execution_use_their_respective_requests(self):
        command = "cat > worker.js <<'JS'\nconsole.log('done')\nJS\nnode worker.js; cat notes.md; ls"
        data, events = self.bash_trace(command, 'done\n' + self.input.read_text() + 'notes.md\n')
        self.assertEqual([(e['operation'], e['request_number']) for e in events], [('write', 1), ('read', 2), ('exec', 2)])
        self.assertEqual(next(e['display_name'] for e in events if e['operation'] == 'exec'), 'node worker.js')
        self.assertTrue(audit(data)['context_coverage_exact'])

    def test_failed_bash_retains_read_proven_by_its_output(self):
        # A later shell error must not erase the cat that already succeeded.
        command = "cat notes.md; echo ======; cat result.md; ls"
        result = 'Exit code 1\n' + self.input.read_text() + '\nshell: separator not found\n'
        data, events = self.bash_trace(command, result, is_error=True)
        reads = [e for e in events if e.get('read_id')]
        self.assertEqual([(e['path'], e['request_number']) for e in reads], [(str(self.input), 2)])
        self.assertEqual(data['sources'][reads[0]['content_ref']['source_id']], self.input.read_text().rstrip('\n'))
        self.assertNotIn('exec', [e['operation'] for e in events])
        self.assertTrue(audit(data)['context_coverage_exact'])

    def test_output_candidates_skip_option_values_and_rank_writes(self):
        self.family()
        modified = datetime.fromisoformat("2026-01-02T00:30:00+00:00").timestamp()
        os.utime(self.output, (modified, modified))

        def command_log(name, command, minute):
            self.log(self.project / (name + ".jsonl"), "Synthetic command.", [([
                {"type": "tool_use", "id": name, "name": "Bash", "input": {"command": command}}
            ], [])], minute - 1)

        for i, flag in enumerate(("--file", "--input", "--future-option")):
            for joined in (False, True):
                option = flag + ("=" if joined else " ") + "'" + str(self.output) + "'"
                command = "python3 -I trace.py find " + option
                self.assertEqual(analyze(command, str(self.root))["writes"], [])
                command_log("reader-%d-%s" % (i, joined), command, 20)
        command_log("inferred", "python3 render.py '%s' '%s'" % (self.input, self.output), 25)
        self.log(self.project / "future.jsonl", "Synthetic future write.", [([
            {"type": "tool_use", "id": "future", "name": "Write", "input": {"file_path": str(self.output), "content": "future"}}
        ], [])], 44)
        found = Catalog(self.root).find(str(self.output))
        self.assertEqual([op["tool_use_id"] for op in found], ["write-article", "inferred"])
        data = build(self.args(from_output=str(self.output)))
        self.assertEqual(data["scope"]["selected_tool_use_id"], "write-article")

        for i, flag in enumerate(("-o", "--output", "--out", "--output-file")):
            command_log("explicit-%d" % i, "python3 render.py %s '%s'" % (flag, self.output), 21 + i)
        found = Catalog(self.root).find(str(self.output))
        self.assertEqual([op["tool_use_id"] for op in found],
                         ["explicit-3", "explicit-2", "explicit-1", "explicit-0", "write-article", "inferred"])


from test_v2 import SegmentTests, OperationTests, OutputSplitTests, ReferenceTests, SidebarTests, ContextTests


if __name__ == "__main__":
    unittest.main()
