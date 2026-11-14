"""Synthetic v2 regressions; never include private recorded text."""
import os
import tempfile
import unittest
from pathlib import Path

from chain import (CATEGORIES, ChainBuilder, command_name, compositions, display_path,
                   event_counts, group_events, initial_context, operation, segment_events)
from file_index import MAX_TEXT_BYTES, ReferenceResolver, build_files, line_ranges
from model import Document, GROUPS
from shell import activities, analyze, command_parts, split_output


def event(eid, number, op='read', path='/tmp/example/a.md', end=None, image=False):
    return dict(id=eid, node_id='n', kind='event', request_number=number, request_id='n/request/' + str(number),
                operation=op, operation_label=op, ends_segment=end, path=path, display_name=Path(path).name,
                directory_hint=display_path(str(Path(path).parent)) + '/', characters=3, is_focus=False,
                item_ids=[], raw_refs=[], content_ref=None, written_files=[], image_ids=['image'] if image else [],
                read_id=eid + '/read' if op == 'read' else None, read_range={'kind': 'full', 'selectors': []},
                output_truncated=False, shared_with=[], comparison_status='same', timestamp='2026-01-01T00:00:00Z')


class SegmentTests(unittest.TestCase):
    def test_writes_merge_but_events_spawn_return_stop_merging(self):
        events = [event('read', 2), event('w1', 2, 'write', end='write'), event('w2', 3, 'write', end='write'),
                  event('shell-edit', 4, 'edit'), event('tool-edit', 5, 'edit', end='write'),
                  event('spawn', 6, 'spawn', end='spawn'), event('w3', 6, 'write', end='write'),
                  event('return', 7, 'return', end='return')]
        data = dict(events={e['id']: e for e in events}, segments={})
        node = dict(id='n', event_ids=list(data['events']))
        segment_events(data, node)
        segments = list(data['segments'].values())
        self.assertEqual([s['event_count'] for s in segments], [1, 1, 0, 0, 0])
        self.assertEqual(segments[0]['ending_event_ids'], ['w1', 'w2'])
        self.assertEqual(segments[0]['ending_request_range'], [2, 3])
        self.assertEqual(segments[1]['event_ids'], ['shell-edit'])
        self.assertEqual(segments[-1]['end_kind'], 'return')

    def test_grouping_threshold_exact_parent_and_images_across_directories(self):
        events = [event('i1', 1, image=True), event('i2', 2, path='/tmp/other/b.png', image=True), event('i3', 2, image=True),
                  event('gap', 3, 'exec'), event('a1', 4), event('a2', 4, path='/tmp/example/b.md'),
                  event('a3', 5, path='/tmp/example/c.md'), event('nested', 5, path='/tmp/example/sub/d.md'),
                  event('j1', 6, image=True), event('j2', 6, image=True)]
        data = dict(events={e['id']: e for e in events})
        grouped = group_events(data, list(data['events']), 'seg')
        groups = [data['events'][g] for g in grouped if data['events'][g]['kind'] == 'group']
        self.assertEqual([g['child_event_ids'] for g in groups], [['i1', 'i2', 'i3'], ['a1', 'a2', 'a3']])
        self.assertIn('nested', grouped)
        self.assertIn('j1', grouped)
        self.assertEqual(sum(event_counts(events).values()), 10)


class OperationTests(unittest.TestCase):
    def test_operation_table(self):
        for command, method, expected in [
            ('cat a.md', 'Bash cat', 'read'), ('head -n 2 a.md', 'Bash head', 'read'),
            ('tail a.md', 'Bash tail', 'read'), ("sed -n '2,4p' a.md", 'Bash sed', 'read'),
            ('nl a.md', 'Bash nl', 'read'), ('grep title a.md', 'Bash grep', 'search'),
            ('rg title a.md', 'Bash rg', 'search'), ('find . -name a.md', None, 'search'),
            ("awk '{print $1}' a.md", 'Bash awk', 'filter'),
            ('cd /tmp; ls -la; ls -R | head -50', None, 'list'),
            ("sed -i '' 's/a/b/' a.md", None, 'edit'),
            ("cat > a.md <<'EOF'\nsynthetic\nEOF", None, 'write'),
            ('python3 run.py', None, 'exec')]:
            with self.subTest(command=command):
                self.assertEqual(operation('Bash', command, method, analyze(command, '/tmp')), expected)
        for tool, expected in [('Read', 'read'), ('Grep', 'search'), ('Glob', 'search'), ('Edit', 'edit'),
                               ('Write', 'write'), ('WebSearch', 'fetch'), ('Agent', 'spawn'), ('SubagentHandback', 'return')]:
            self.assertEqual(operation(tool), expected)

    def test_command_name_and_directory_aliases(self):
        self.assertEqual(command_name('cd /tmp; mkdir -p output; W=demo; python3 run.py --mode short', '/tmp'), 'python3 run.py --mode short')
        self.assertLessEqual(len(command_name('echo ' + 'x' * 100, '/tmp')), 60)
        self.assertEqual(display_path('/private/tmp/claude-12/session/scratchpad/a/b.md'), 'scratchpad/a/b.md')
        self.assertEqual(display_path(str(Path.home() / '.claude/projects/project/session-id/tool-results/a.txt')), 'tool-results/a.txt')
        self.assertEqual(display_path(str(Path.home() / '.claude/projects/project/session-id/tool-results')), 'tool-results')
        self.assertEqual(display_path(str(Path.home() / '.claude/projects/project/session-id/subagents/agent-a.jsonl')), 'subagents/agent-a.jsonl')
        self.assertEqual(display_path('/private/tmp/claude-12/session/scratchpad'), 'scratchpad')
        self.assertEqual(display_path('/tmp/work/references/a.md', '/tmp/work'), 'references/a.md')
        self.assertEqual(display_path(str(Path.home() / 'claudecode_workspace/内容/a.md')), '内容/a.md')

    def test_listing_loop_and_original_redirection_spelling(self):
        command = 'ls first second 2>/dev/null; for d in first second; do ls "$d"; echo done; done'
        self.assertEqual(operation('Bash', command, shell=analyze(command, '/tmp')), 'list')
        self.assertEqual(command_name(command, '/tmp'), 'ls first second 2>/dev/null')
        mixed = 'ls first; for d in first; do node "$d/run.js"; done'
        self.assertEqual(operation('Bash', mixed, shell=analyze(mixed, '/tmp')), 'exec')

    def test_nested_substitution_does_not_turn_program_text_into_a_command(self):
        command = 'for f in *.md; do echo "$(python3 -c "import re;\nprint(2)")"; done'
        parts = command_parts(command)
        self.assertEqual([p['tokens'][0] for p in parts], ['echo'])
        self.assertEqual(activities(command, '/tmp')[0]['kind'], 'exec')
        self.assertEqual(command_name(command, '/tmp'), 'for f in *.md')

    def test_loop_execution_title_uses_header_not_assignment_or_body(self):
        command = 'cd /tmp; for f in image3 image4 image5; do d=$(ffprobe -v error -show_entries format=duration "$f.gif"); echo "$d"; done'
        self.assertEqual(command_name(command, '/tmp'), 'for f in image3 image4 image5')
        execution = next(p for p in activities(command, '/tmp') if p['kind'] == 'exec')
        self.assertEqual(command_name(execution['display_raw'], '/tmp'), 'for f in image3 image4 image5')
        self.assertFalse(execution['tokens'][0].startswith('-'))
        self.assertLessEqual(len(command_name('for f in ' + 'image ' * 20 + '; do node "$f"; done', '/tmp')), 60)

    def test_queued_message_is_user_event(self):
        doc = Document({}, {})
        node = dict(id='n', agent_id=None, cwd='/tmp', range={'start': 1, 'end': 1},
                    request_ids=['n/request/1'], groups={g: [] for g in GROUPS})
        item = doc.item(node, 'reminders', 'q', '中途用户消息', kind='attachment', attachment_type='queued_command')
        item.update(first_request=1, display_ref=doc.ref('<system-reminder>new user instruction</system-reminder>'))
        doc.data.update(events={}, segments={}, requests={'n/request/1': {'id': 'n/request/1', 'number': 1, 'timestamp': '2026-01-01T00:00:00Z'}})
        ChainBuilder(doc, node).build()
        row = doc.data['events'][node['event_ids'][0]]
        self.assertEqual(row['operation'], 'user')
        self.assertEqual(row['display_name'], '用户消息（运行中插入）')

    def test_skill_tool_injection_is_a_read_of_skill_md(self):
        with tempfile.TemporaryDirectory() as root:
            skill = Path(root, 'demo-skill')
            skill.mkdir()
            (skill / 'SKILL.md').write_text('---\nname: demo\ndescription: x\n---\n\n# demo\n\nstep one\n', encoding='utf-8')
            injected = 'Base directory for this skill: %s\n\n# demo\n\nstep one\n\n\nARGUMENTS: make a poster' % skill
            results = {}
            for label, text in (('same', injected), ('different', injected.replace('step one', 'step two'))):
                doc = Document({}, {})
                node = dict(id='n', agent_id=None, cwd=root, range={'start': 1, 'end': 1},
                            request_ids=['n/request/1'], groups={g: [] for g in GROUPS})
                item = doc.item(node, 'upstream', 's', '用户消息', kind='message')
                item.update(first_request=1, display_ref=doc.ref(text))
                doc.data.update(events={}, segments={}, requests={'n/request/1': {'id': 'n/request/1', 'number': 1, 'timestamp': '2026-01-01T00:00:00Z'}})
                ChainBuilder(doc, node).build()
                results[label] = doc.data['events'][node['event_ids'][0]]
            row = results['same']
            self.assertEqual((row['operation'], row['method'], row['display_name']), ('read', 'Skill', 'SKILL.md'))
            self.assertEqual(row['path'], os.path.realpath(skill / 'SKILL.md'))
            self.assertEqual(row['file_access'], 'read')
            self.assertEqual(row['comparison_status'], 'same')
            self.assertEqual(results['different']['comparison_status'], 'different')


class OutputSplitTests(unittest.TestCase):
    def test_repeated_echo_markers_and_grep_partition(self):
        analysis = analyze("cat a.md; echo '----'; ls; echo '----'; grep topic b.md | head -3", '/tmp')
        a, b = [r['path'] for r in analysis['reads']]
        result = split_output(analysis, '# Header\ntext\n----\nlisting\n----\n8:topic\n', [a, b])
        self.assertEqual(result[b]['text'], '8:topic\n')
        self.assertEqual(result[a]['text'], '# Header\ntext\n')
        self.assertEqual(result[b]['shared_with'], [])

    def test_ambiguous_output_retains_peers(self):
        paths = ['/tmp/a.md', '/tmp/b.md']
        for command, text in [('cat a.md b.md', 'combined'),
                              ("cat a.md; echo '---'; cat b.md", 'a\n--- extra\nb'),
                              ("cat a.md; echo '---'; cat b.md", 'a\n---\n---\nb')]:
            with self.subTest(command=command, text=text):
                result = split_output(analyze(command, '/tmp'), text, paths)
                self.assertFalse(result[paths[0]]['split'])
                self.assertEqual(result[paths[0]]['text'], text)
                self.assertEqual(result[paths[0]]['shared_with'], [paths[1]])


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        for name in ['skill/SKILL.md', 'skill/references/写法.md', 'skill/references/体裁/索引.md',
                     'skill/references/问作者.md', 'profile/关于我.md', 'cwd/local.md', 'skill/with space.md']:
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('synthetic')
        self.source = str(self.root / 'skill/SKILL.md')
        self.cwd = str(self.root / 'cwd')

    def test_five_levels_and_unicode_offsets(self):
        known = [str(self.root / p) for p in ('skill/references/写法.md', 'profile/关于我.md')]
        resolver = ReferenceResolver(known)
        for token, suffix, level in [
            (str(self.root / 'profile/关于我.md'), 'profile/关于我.md', 1),
            ('references/写法.md', 'skill/references/写法.md', 2), ('local.md', 'cwd/local.md', 3),
            ('写法.md', 'skill/references/写法.md', 4), ('关于我.md', 'profile/关于我.md', 4),
            ('体裁/索引.md', 'skill/references/体裁/索引.md', 5), ('references/问作者.md', 'skill/references/问作者.md', 2)]:
            self.assertEqual(resolver.resolve(token, self.source, self.cwd), (str(self.root / suffix), level))
        text = '😀「写法.md」以及 `references/问作者.md`，还有 `with space.md`。'
        refs = resolver.scan(text, self.source, self.cwd)
        self.assertEqual([text[row[0]:row[1]] for row in refs], ['写法.md', 'references/问作者.md', 'with space.md'])
        self.assertEqual(refs[0][0], 2)

    def test_ambiguity_and_nonexistent_files(self):
        duplicate = self.root / 'other/关于我.md'
        duplicate.parent.mkdir()
        duplicate.write_text('other')
        resolver = ReferenceResolver([str(duplicate), str(self.root / 'profile/关于我.md')])
        self.assertIsNone(resolver.resolve('关于我.md', self.source, self.cwd))
        self.assertIsNone(resolver.resolve('missing.md', self.source, self.cwd))
        self.assertIsNone(resolver.resolve('https://example.test/关于我.md', self.source, self.cwd))

    def test_directories_use_five_levels_and_require_directory_spelling(self):
        (self.root / 'cwd/images').mkdir()
        (self.root / 'skill/with space').mkdir()
        (self.root / 'skill/archive.md').mkdir()
        resolver = ReferenceResolver([str(self.root / p) for p in ('skill/references/写法.md', 'profile/关于我.md')])
        for token, path, level in [
            (str(self.root / 'profile'), self.root / 'profile', 1),
            ('~/', Path.home().resolve(), 1),
            ('references/', self.root / 'skill/references', 2),
            ('images/', self.root / 'cwd/images', 3),
            ('profile/', self.root / 'profile', 4),
            ('体裁/', self.root / 'skill/references/体裁', 5),
            ('with space/', self.root / 'skill/with space', 2),
            (str(self.root / 'skill/archive.md'), self.root / 'skill/archive.md', 1),
        ]:
            with self.subTest(token=token):
                text = '😀 `' + token + '`。'
                self.assertEqual(resolver.scan(text, self.source, self.cwd), [(3, 3 + len(token), str(path), level, 'dir')])
        self.assertEqual(resolver.scan('references', self.source, self.cwd), [])

    def test_directory_ambiguity_nonexistence_and_full_file_paths(self):
        known = []
        for name in ('one/shared/a.md', 'two/shared/b.md'):
            p = self.root / name
            p.parent.mkdir(parents=True)
            p.write_text('synthetic')
            known.append(str(p))
        for name in ('skill/nested/shared', 'skill/a/assets', 'skill/b/assets'):
            (self.root / name).mkdir(parents=True)
        resolver = ReferenceResolver(known)
        for token in ('shared/', 'assets/', 'missing/', str(self.root / 'missing'), 'https://example.test/references/'):
            self.assertEqual(resolver.scan(token, self.source, self.cwd), [])
        text = 'references/ references/写法.md references/missing.md'
        found = resolver.scan(text, self.source, self.cwd)
        self.assertEqual([(text[a:b], kind) for a, b, _, _, kind in found], [('references/', 'dir'), ('references/写法.md', 'file')])


class SidebarTests(unittest.TestCase):
    def test_directory_references_do_not_create_sidebar_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / 'references').mkdir()
            (root / 'references/a.md').write_text('synthetic')
            doc = Document({}, {})
            node = dict(id='n', cwd=str(root), end='2026-01-01T00:00:00Z', groups={g: [] for g in GROUPS})
            user = event('user', 1, 'user', path=str(root / 'task.md'))
            user.update(content_ref=doc.ref('references/ references/a.md'))
            doc.data.update(nodes=[node], events={'user': user}, file_references=[], files={})
            build_files(doc)
            refs = doc.data['file_references']
            self.assertEqual([ref['kind'] for ref in refs], ['dir', 'file'])
            self.assertIsNone(refs[0]['file_id'])
            self.assertNotIn(str(root / 'references'), doc.data['files'])
            self.assertEqual(refs[1]['file_id'], doc.data['files'][str(root / 'references/a.md')]['id'])

    def test_ranges_require_deterministic_line_mapping(self):
        e = event('e', 2)
        e['read_range'] = dict(kind='partial', selectors=[dict(method='Read', offset=2, limit=3)])
        self.assertEqual(line_ranges(e, 10), [dict(start=2, end=4, kind='lines')])
        e['read_range']['selectors'] = [dict(method='head', lines='5'), dict(method='sed', ranges=[[2, 3]])]
        self.assertEqual(line_ranges(e, 10), [dict(start=2, end=3, kind='lines')])
        for selector in [dict(method='grep'), dict(method='head', bytes='200'), dict(method='awk')]:
            e['read_range']['selectors'] = [selector]
            self.assertEqual(line_ranges(e, 10), [])
        e['read_range'] = dict(kind='full', selectors=[])
        e['output_truncated'] = True
        self.assertEqual(line_ranges(e, 10), [])

    def test_changed_last_read_unread_reference_image_and_size_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            for name, text in [('same.md', 'full\n'), ('changed.md', 'new\n'), ('unread.md', 'unread\n')]:
                (root / name).write_text(text)
            (root / 'big.md').write_bytes(b'x' * (MAX_TEXT_BYTES + 1))
            (root / 'image.png').write_bytes(b'image')
            doc = Document({}, {})
            doc.data.update(events={}, files={}, file_references=[])
            node = dict(id='n', cwd=str(root), end='2026-01-01T00:00:00Z', groups={g: [] for g in GROUPS})
            doc.data['nodes'] = [node]
            for name, text, status in [('same.md', 'full', 'same'), ('changed.md', 'old', 'different')]:
                e = event(name, 8, path=str(root / name))
                e.update(content_ref=doc.ref(text), comparison_status=status)
                doc.data['events'][e['id']] = e
            user = event('user', 1, 'user')
            user.update(content_ref=doc.ref('unread.md big.md image.png'), path=None)
            doc.data['events']['user'] = user
            build_files(doc)
            files = doc.data['files']
            self.assertEqual(files[str(root / 'same.md')]['content_version'], 'current')
            self.assertEqual(files[str(root / 'same.md')]['read_ranges'][0]['kind'], 'full')
            changed = files[str(root / 'changed.md')]
            self.assertEqual(changed['content_version'], 'last_read')
            self.assertEqual(doc.resolve(changed['content_ref']), 'old')
            self.assertEqual(changed['last_read_request_number'], 8)
            self.assertEqual(files[str(root / 'unread.md')]['event_ids'], [])
            self.assertEqual(doc.resolve(files[str(root / 'unread.md')]['content_ref']), 'unread\n')
            self.assertIsNone(files[str(root / 'big.md')]['content_ref'])
            self.assertEqual(files[str(root / 'big.md')]['omitted_reason'], 'over_1mb')
            self.assertEqual(files[str(root / 'image.png')]['image_ids'], [])
            self.assertEqual(files[str(root / 'image.png')]['content_version'], 'path_only')


class ContextTests(unittest.TestCase):
    def test_main_initial_context_is_first_request_snapshot_including_prior_conversation(self):
        doc = Document({}, {})
        node = dict(id='n', agent_id=None, groups={g: [] for g in GROUPS}, request_ids=['r1'])
        first_ids, ownership = [], []
        for group, key, value in [('system', 's', 'system'), ('tools', 't', {'name': 'Read', 'description': 'read'}),
                                  ('automatic', 'a', 'initial injection'), ('automatic', 'late', 'later injection'),
                                  ('upstream', 'u', 'new user message'), ('before_range', 'old', 'earlier dialogue')]:
            item = doc.item(node, group, key, key)
            item.update(display_ref=doc.ref(value), characters=len(str(value)), first_request=2 if key == 'late' else 1)
            if key != 'late':
                first_ids.append(item['id'])
                ownership.append(dict(owner_id=item['id'], raw_ref=item['display_ref']))
        doc.data['requests']['r1'] = dict(id='r1', context_item_ids=first_ids, ownership=ownership)
        initial_context(doc, node)
        categories = node['initial_context']['categories']
        self.assertEqual(set(categories), {'system', 'tools', 'injected', 'history'})
        self.assertEqual(len(categories['injected']['entries']), 1)
        self.assertEqual(categories['history']['characters'], len('earlier dialogue'))
        self.assertEqual([doc.resolve(ref) for ref in categories['history']['entries'][0]['content_refs']], ['earlier dialogue'])

    def test_composition_uses_request_ownership_not_cumulative_event_sizes(self):
        doc = Document({}, {})
        node = dict(id='n', groups={g: [] for g in GROUPS}, event_ids=['old', 'new'], segment_ids=['s'])
        doc.data.update(nodes=[node], events={}, segments={}, context_compositions={})
        ownership = []
        for group, key, text in [('system', 'system', 'sys'), ('tools', 'tools', {'name': 'Read', 'description': 'read', 'input_schema': {}}),
                                 ('automatic', 'injected', 'inject'), ('upstream', 'task', 'task'),
                                 ('files', 'old', 'old'), ('files', 'new', 'new'),
                                 ('requests', 'model', {'type': 'thinking', 'thinking': 'think', 'signature': 'ignored'}),
                                 ('reminders', 'reminders', 'notice')]:
            item = doc.item(node, group, key, key)
            ref = doc.ref(text)
            ownership.append(dict(owner_id=item['id'], related_ids=[], raw_ref=ref))
            if key in ('old', 'new'):
                e = event(key, 2 if key == 'old' else 3)
                e.update(item_ids=[item['id']], raw_refs=[ref], segment_id='earlier' if key == 'old' else 's')
                doc.data['events'][key] = e
        doc.data['segments']['s'] = dict(context_request_id='n/request/4')
        doc.data['requests']['n/request/4'] = dict(id='n/request/4', number=4, ownership=ownership)
        compositions(doc, node)
        composition = doc.data['context_compositions']['s/context']
        cats = composition['categories']
        self.assertEqual(set(cats), set(CATEGORIES))
        self.assertEqual(cats['previous']['event_ids'], ['old'])
        self.assertEqual(cats['current']['event_ids'], ['new'])
        self.assertEqual(cats['model']['characters'], 5)
        self.assertEqual(composition['characters'], sum(c['characters'] for c in cats.values()))


if __name__ == '__main__':
    unittest.main()
