"""v2 chronological projection. v1 evidence and ownership remain intact."""
import json
import re
import os
from collections import defaultdict
from pathlib import Path

from provenance import comparison, visible_text
from records import blocks, digest, text_content
from shell import activities, analyze, command_parts, path_of, raw_segments, segments, split_output

OPERATIONS = dict(read='读取', search='查找', filter='过滤', list='列出', exec='执行',
                  write='写入', edit='编辑', fetch='抓取', spawn='调用',
                  return_='返回', reminder='提醒', user='用户', reply='回复', think='思考')
OPERATIONS['return'] = OPERATIONS.pop('return_')
# 代码与命令：执行、列出，以及对代码文件的读写。写代码文件、图片和音视频不切段，写其余文档（不论用哪个工具）都切段。
CODE_FILE = re.compile(r'\.(?:py|js|mjs|cjs|ts|tsx|jsx|sh|zsh|bash|rb|go|rs|java|swift|sql|css|html?)$', re.I)  # 11-04 用户：html 也算代码
MEDIA_FILE = re.compile(r'\.(?:png|jpe?g|gif|webp|svg|bmp|ico|heic|mp4|mov|webm|mp3|wav|m4a)$', re.I)


def is_document(path):
    return bool(path) and not CODE_FILE.search(path) and not MEDIA_FILE.search(path)


def is_code(e):
    if e['operation'] in ('exec', 'list'):
        return True
    return (e['operation'] in ('read', 'search', 'filter', 'write', 'edit') and not e.get('image_ids')
            and bool(CODE_FILE.search(e.get('path') or '')))
CATEGORIES = dict(system='系统提示词', tools='工具定义', injected='注入内容', task='任务提示词',
                  previous='之前分段的事件', current='本分段的事件', model='模型输出', reminders='提醒')


def display_path(path, cwd=None):
    path = os.path.expanduser(str(path))
    scratch = re.search(r'/private/tmp/claude-[^/]+/(?:.*/)?scratchpad(?:/(.*))?$', path)
    if scratch:
        return 'scratchpad' + ('/' + scratch[1] if scratch[1] else '')
    tool = re.search(r'/\.claude/projects/[^/]+/[^/]+/tool-results(?:/(.*))?$', path)
    if tool:
        return 'tool-results' + ('/' + tool[1] if tool[1] else '')
    session_child = re.search(r'/\.claude/projects/[^/]+/[^/]+/(.*)', path)
    if session_child:
        return session_child[1]
    for root in (cwd, str(Path.home() / 'claudecode_workspace')):
        if root:
            try:
                return str(Path(path).relative_to(root))
            except ValueError:
                pass
    home = str(Path.home())
    return '~' + path[len(home):] if path == home or path.startswith(home + '/') else path


def skill_comparison(path, body):
    """SKILL.md loaded by the Skill tool arrives without its frontmatter."""
    p = Path(path) if path else None
    if not p or not p.is_file():
        return comparison(path or '')
    try:
        now = p.read_text(encoding='utf-8')
    except (UnicodeError, OSError):
        return comparison(path)
    front = re.match(r'---\n.*?\n---\n', now, re.S)
    if (now[front.end():] if front else now).strip() == body.strip():
        return {'status': 'same', 'label': '和现在一致', 'basis': '去掉 frontmatter 后全文逐字符比较', 'diff': None}
    return comparison(path, body, full=False)


def meaningful_parts(command):
    return [part['tokens'] for part in command_parts(command)
            if Path(part['tokens'][0]).name != 'cd' and not (Path(part['tokens'][0]).name == 'mkdir' and '-p' in part['tokens'])]


def operation(tool, command='', method=None, shell=None):
    if tool != 'Bash':
        return {'Read': 'read', 'Grep': 'search', 'Glob': 'search', 'Write': 'write',
                'Edit': 'edit', 'WebFetch': 'fetch', 'WebSearch': 'fetch',
                'Agent': 'spawn', 'Task': 'spawn', 'SubagentHandback': 'return'}.get(tool, 'exec')
    parts = meaningful_parts(command)
    if method:
        names = method.replace('Bash ', '').split(' / ')
        if 'awk' in names:
            return 'filter'
        if any(n in ('grep', 'rg', 'find') for n in names):
            return 'search'
        return 'read'
    if any(Path(p[0]).name == 'sed' and any(a.startswith(('-i', '--in-place')) for a in p[1:]) for p in parts):
        return 'edit'
    names = [Path(p[0]).name for p in parts]
    work = activities(command, None)
    if any(p['kind'] == 'list' for p in work) and all(p['kind'] in ('list', 'aux', 'read') for p in work) and not (shell or {}).get('reads'):
        return 'list'
    if names and all(n in ('grep', 'rg', 'find') for n in names):
        return 'search'
    if shell and shell['writes'] and not shell['reads'] and names and all(n in ('cat', 'echo', 'printf', 'tee') for n in names):
        return 'write'
    return 'exec'


def command_name(command, cwd):
    parts = [p for p in command_parts(command) if Path(p['tokens'][0]).name != 'cd' and not (Path(p['tokens'][0]).name == 'mkdir' and '-p' in p['tokens'])]
    loop_header = re.match(r'^\s*(?:for|select)\s', command)
    if loop_header:
        name = raw_segments(command)[0][0]
    elif parts:
        name = parts[0]['display_raw']
    else:
        return 'Bash'
    parsed = segments(name)
    tokens = parsed[0][0] if parsed else []
    # Inline program bodies are content, not command names.
    if tokens and Path(tokens[0]).name in ('python', 'python3', 'node', 'bash', 'sh'):
        for flag in ('-c', '-e', '--eval'):
            if flag in tokens:
                match = re.search(r'(?<!\S)' + re.escape(flag) + r'(?=\s)', name)
                if match:
                    name = name[:match.end()] + ' …'
                break
    for token in tokens:
        if token.startswith(('/', '~/')):
            name = name.replace(token, display_path(token, cwd))
    name = name.replace('\n', ' ')
    return name[:59] + '…' if len(name) > 60 else name


def covered_characters(ranges):
    """Union of code-point spans, so shared read output is deducted once."""
    total, end = 0, 0
    for a, b in sorted(ranges):
        total += max(0, b - max(a, end))
        end = max(end, b)
    return total


def content_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ''.join(content_text(v) for v in value)
    if not isinstance(value, dict):
        return ''
    if value.get('type') in ('image', 'document'):
        return ''
    if value.get('type') == 'thinking':
        return value.get('thinking', '')
    if 'content' in value:
        return content_text(value['content'])
    return value.get('text', '')


def event_counts(events):
    counts = {k: 0 for k in OPERATIONS}
    for e in events:
        counts[e['operation']] += 1
    return counts


def group_events(data, ids, key):
    """D2 groups are presentation nodes; leaf counts never change."""
    result, run, previous = [], [], None

    def flush():
        if len(run) < 3:
            result.extend(run)
            return
        children = [data['events'][eid] for eid in run]
        gid = key + '/group/' + digest(run)[:16]
        kind, directory = previous
        group = dict(children[0], id=gid, kind='group', child_event_ids=list(run),
                     display_name='读取图片 ×%d' % len(run) if kind == 'image' else '读取 %s 下 %d 个文件' % (children[0]['directory_hint'], len(run)),
                     request_range=[children[0]['request_number'], children[-1]['request_number']],
                     characters=sum(e['characters'] for e in children),
                     visible_characters=sum(e.get('visible_characters', e['characters']) for e in children),
                     is_focus=any(e['is_focus'] for e in children))
        for field in ('path', 'read_id', 'content_ref', 'call_ref', 'raw_refs', 'item_ids', 'written_files', 'image_ids'):
            group.pop(field, None)
        data['events'][gid] = group
        result.append(gid)

    for eid in ids:
        e = data['events'][eid]
        candidate = ('image', '') if e.get('image_ids') and e['operation'] == 'read' else ('files', str(Path(e['path']).parent)) if e.get('read_id') and e['operation'] == 'read' else None
        if candidate is None or candidate != previous:
            flush()
            run = []
        if candidate:
            run.append(eid)
        else:
            result.append(eid)
        previous = candidate
    flush()
    return result


def trace_rows(data, node):
    """Time-ordered rows: consecutive inputs fold into one 输入 ×N row; outputs and user messages stand alone."""
    events, rows, run = data['events'], [], []

    def flush():
        if len(run) == 1:
            rows.append(run[0])
        elif run:
            children = [events[eid] for eid in run]
            gid = node['id'] + '/inputs/' + str(len(rows) + 1)
            counts = event_counts(children)
            events[gid] = dict(id=gid, node_id=node['id'], kind='inputs', operation='inputs', operation_label='输入',
                               display_name='输入 ×%d' % len(run), child_event_ids=group_events(data, list(run), gid),
                               event_count=len(run), request_range=[children[0]['request_number'], children[-1]['request_number']],
                               request_number=children[0]['request_number'], request_id=children[0]['request_id'],
                               timestamp=children[0].get('timestamp'), operation_counts=counts,
                               image_count=sum(bool(e.get('image_ids')) for e in children),
                               characters=sum(e['characters'] for e in children), is_focus=any(e['is_focus'] for e in children),
                               is_output=False, directory_hint='', ends_segment=None)
            for e in children:
                e['input_group_id'] = gid
            rows.append(gid)
        run.clear()

    for eid in node['event_ids']:
        if eid in node.get('leading_event_ids', []):
            continue
        e = events[eid]
        if e['is_output'] or e['operation'] == 'user':
            flush()
            rows.append(eid)
        else:
            run.append(eid)
    flush()
    return rows


def segment_events(data, node):
    segments_out, pending = [], []
    events = data['events']
    for eid in node['event_ids']:
        if eid in node.get('leading_event_ids', []):
            continue
        e = events[eid]
        end = e.get('ends_segment')
        if not end:
            pending.append(eid)
            continue
        merge = end == 'write' and not pending and segments_out and segments_out[-1]['end_kind'] == 'write'
        if merge:
            s = segments_out[-1]
            s['ending_event_ids'].append(eid)
        else:
            sid = node['id'] + '/segment/' + str(len(segments_out) + 1)
            s = dict(id=sid, node_id=node['id'], number=len(segments_out) + 1,
                     end_kind=end, event_ids=pending, ending_event_ids=[eid])
            pending = []
            segments_out.append(s)
    if pending:
        sid = node['id'] + '/segment/' + str(len(segments_out) + 1)
        segments_out.append(dict(id=sid, node_id=node['id'], number=len(segments_out) + 1,
                                 end_kind='open', event_ids=pending, ending_event_ids=[]))
    for s in segments_out:
        all_ids = s['event_ids'] + s['ending_event_ids']
        numbers = [events[e]['request_number'] for e in all_ids]
        ending_numbers = [events[e]['request_number'] for e in s['ending_event_ids']]
        s.update(request_range=[min(numbers), max(numbers)], ending_request_range=[min(ending_numbers), max(ending_numbers)] if ending_numbers else None,
                 context_request_id=events[all_ids[-1]]['request_id'], event_count=len(s['event_ids']),
                 operation_counts=event_counts(events[e] for e in s['event_ids']),
                 image_count=sum(bool(events[e].get('image_ids')) for e in s['event_ids']),
                 writes=[dict(w, event_id=e) for e in s['ending_event_ids'] for w in events[e].get('written_files', [])])
        s['tree_event_ids'] = group_events(data, s['event_ids'], s['id'])
        for eid in all_ids:
            events[eid]['segment_id'] = s['id']
        data['segments'][s['id']] = s
    node['segment_ids'] = [s['id'] for s in segments_out]


class ChainBuilder:
    def __init__(self, doc, node):
        self.doc, self.d, self.node = doc, doc.data, node
        self.items = [self.d['items'][iid] for ids in node['groups'].values() for iid in ids]
        self.calls, self.writes, self.reads, self.commands = {}, defaultdict(list), defaultdict(list), {}
        self.results, seen_messages = {}, set()
        self.events = []
        self.order = {}
        for rid in node['request_ids']:
            req = self.d['requests'][rid]
            for sid in req.get('message_source_ids', []):
                if sid in seen_messages:
                    continue
                seen_messages.add(sid)
                message = self.d['sources'][sid]
                for i, b in enumerate(blocks(message.get('content', []))):
                    if b.get('type') == 'tool_result':
                        self.results.setdefault(b['tool_use_id'], (req, b, dict(source_id=sid, pointer='/content/' + str(i))))
            if req.get('response_ref'):
                message = doc.resolve(req['response_ref'])
                for i, b in enumerate(blocks(message.get('content', []))):
                    if b.get('type') == 'tool_use':
                        self.calls[b['id']] = (b, req, dict(req['response_ref'], pointer='/content/' + str(i)))
                        self.order[b['id']] = len(self.order)
        for item in self.items:
            for w in item.get('writes', []):
                if w.get('confidence') != 'ambiguous_argument':
                    self.writes[w['tool_use_id']].append((item, w))
            for r in item.get('reads', []):
                self.reads[r['tool_use_id']].append((item, r))
            if item.get('kind') == 'tool_output':
                self.commands[item['tool_use_id']] = item

    def make(self, key, operation_key, number, **fields):
        rid = self.node['id'] + '/request/' + str(number)
        e = dict(id=self.node['id'] + '/event/' + key, node_id=self.node['id'], kind='event',
                 request_id=rid, request_number=number, operation=operation_key, operation_label=OPERATIONS[operation_key],
                 timestamp=self.d['requests'].get(rid, {}).get('timestamp'), method='', display_name='', directory_hint='',
                 characters=0, is_focus=False, item_ids=[], raw_refs=[], content_ref=None, written_files=[], image_ids=[],
                 read_range=None, output_truncated=False, failed=False, comparison_status='unavailable',
                 ends_segment=None, **fields)
        self.events.append(e)
        return e

    def build(self):
        selected = self.d['scope'].get('selected_tool_use_id')
        for tid, (call, req, ref) in self.calls.items():
            name, inp = call['name'], call.get('input', {})
            command = inp.get('command', '')
            shell = analyze(command, self.node['cwd']) if name == 'Bash' else None
            work = activities(command, self.node['cwd']) if name == 'Bash' else []
            written = [dict(path=i['path'], item_id=i['id'], write_id=w['id'], method=w['method'],
                            content_ref=w.get('content_ref'), before_ref=w.get('before_ref'), after_ref=w.get('after_ref'),
                            timestamp=w['timestamp'], content_kind=w.get('content_kind', 'full'), failed=w.get('is_error', False)) for i, w in self.writes[tid]]
            baseop = operation(name, command, shell=shell)
            if name == 'SubagentHandback':
                continue  # one canonical handback item below
            if baseop == 'spawn':
                edge = next((e for e in self.d['edges'] if e['kind'] == 'dispatch' and e['tool_use_id'] == tid), None)
                if edge is None:
                    # Parallel calls outside the selected producer chain stay
                    # in raw requests, not in this trace's navigation tree.
                    continue
                e = self.make(tid, 'spawn', req['number'])
                e.update(method=name, display_name=inp.get('description') or '子代理', call_ref=ref, raw_refs=[ref],
                         content_ref=self.doc.ref(inp.get('prompt', '')), characters=len(inp.get('prompt', '')),
                         child_node_id=edge['child_node_id'] if edge else None, ends_segment='spawn',
                         item_ids=[edge['parent_item_id']] if edge else [])
                continue
            call_writes = []
            for index, w in enumerate(written):
                op = 'edit' if name == 'Edit' or w['method'] in ('命令改了它', '命令追加') else 'write'
                ending = is_document(w['path']) or (tid == selected and w['path'] == self.d['scope'].get('from_output'))
                e = self.make(tid + '/write/' + str(index), op, req['number'])
                method = 'Bash ' + next((Path(p['tokens'][0]).name for p in work if p['kind'] == 'write'), '脚本') if name == 'Bash' else name
                e.update(method=method, display_name=Path(w['path']).name, path=w['path'], written_files=[w], call_ref=ref, raw_refs=[ref],
                         item_ids=[w['item_id']], ends_segment='write' if ending else None, failed=w['failed'], timestamp=w['timestamp'])
                e['content_ref'] = w.get('content_ref') or w.get('after_ref')
                if e['content_ref']:
                    e['characters'] = len(content_text(self.doc.resolve(e['content_ref'])))
                call_writes.append(e)
            reads = self.reads.get(tid, [])
            read_output_ranges = []
            if reads:
                result = self.doc.resolve(reads[0][1]['raw_ref'])
                raw_text = content_text(result)
                splits = split_output(shell, raw_text, [i['path'] for i, r in reads]) if shell else {}
                for index, (item, r) in enumerate(reads):
                    piece = splits.get(item['path'], dict(text=raw_text, shared_with=r['shared_with'], split=False, ranges=[[0, len(raw_text)]]))
                    if r.get('result_text_slice'):
                        part = r['result_text_slice']
                        piece = dict(text=raw_text[part['start']:part['end']], shared_with=[], split=True, ranges=[[part['start'], part['end']]])
                    read_output_ranges.extend(piece['ranges'])
                    text, trunc = visible_text(piece['text'], r['method'])
                    op = operation(name, command, r['method'], shell)
                    e = self.make(tid + '/read/' + str(index), op, r['request'])
                    comp = comparison(item['path'], text, full=r['coverage']['kind'] == 'full',
                                      shared=bool(piece['shared_with']), image_hashes=r['image_ids'], read_timestamp=r['timestamp'])
                    e.update(path=item['path'], read_id=r['id'], item_ids=[item['id']], method=r['method'],
                             display_name=Path(item['path']).name, content_ref=self.doc.ref(text),
                             call_ref=r['call_ref'], raw_refs=[r['raw_ref']], characters=len(piece['text']), image_ids=r['image_ids'],
                             read_range=r['coverage'], output_truncated=bool(trunc or r['truncation']),
                             truncation=trunc or r['truncation'], comparison_status=comp['status'], comparison=comp,
                             shared_with=piece['shared_with'], output_split=piece['split'], timestamp=r['timestamp'],
                             producer_edge_ids=r['producer_edge_ids'], failed=r.get('is_error', bool(result.get('is_error'))),
                             call_failed=bool(result.get('is_error')), output_partition='matched_file_content' if r.get('result_text_slice') else 'echo' if piece['split'] else 'shared')
                for write_event in call_writes:
                    w = write_event['written_files'][0]
                    read_event = next((e for e in reversed(self.events) if e.get('read_id') and e.get('path') == w['path'] and e['call_ref'] == ref), None)
                    if read_event and not w.get('content_ref') and not read_event['shared_with'] and read_event['read_range']['kind'] == 'full' and not read_event['output_truncated']:
                        w['content_ref'] = read_event['content_ref']
                        w['content_request_id'] = read_event['request_id']
                        write_event['content_ref'] = read_event['content_ref']
                        write_event['characters'] = read_event['characters']
            # All result-based rows share the first request containing the
            # result, even when v1 has only file owners and no commands item.
            observed = self.results.get(tid)
            if observed is None or name in ('Write', 'Edit'):
                continue
            result_req, result, result_ref = observed
            choices = []
            if name == 'Bash':
                extra = next((p for p in work if p['kind'] == 'exec'), None)
                listing = next((p for p in work if p['kind'] == 'list'), None)
                # Keep one call-level result row: extra execution, or a listing
                # when no file-read rows already represent the tool output.
                first = extra or (listing if not reads else None)
                if first:
                    choices.append((first['kind'], first['display_raw'], 'Bash ' + Path(first['tokens'][0]).name))
                if not choices and not reads and not written:
                    first = next((p for p in work if p['kind'] == 'read'), None)
                    fallback = operation('Bash', command, 'Bash ' + Path(first['tokens'][0]).name, shell) if first else baseop
                    choices.append((fallback, first['display_raw'] if first else command, 'Bash'))
            elif not reads:
                choices.append((baseop, '', name))
            item = self.commands.get(tid)
            item_ids = list(dict.fromkeys(([item['id']] if item else []) + [i['id'] for i, _ in reads]))
            for op, title_command, method in choices:
                text, trunc = visible_text(content_text(result))
                e = self.make(tid + '/' + op, op, result_req['number'])
                e.update(method=method, display_name=command_name(title_command, self.node['cwd']) if name == 'Bash' else name,
                         call_ref=ref, raw_refs=[result_ref], content_ref=self.doc.ref(text), characters=len(content_text(result)),
                         item_ids=item_ids, output_truncated=bool(trunc), truncation=trunc,
                         failed=bool(result.get('is_error')), result_shared=bool(reads or len(choices) > 1))
                if reads:
                    e['characters'] -= covered_characters(read_output_ranges)
                if name == 'Read' and inp.get('file_path'):
                    e.update(path=path_of(inp['file_path'], self.node['cwd']), file_access='read',
                             display_name=Path(inp['file_path']).name, read_range={'kind': 'unknown', 'selectors': []})
                if name == 'Grep' and inp.get('path'):
                    path = path_of(inp['path'], self.node['cwd'])
                    if path and Path(path).is_file():
                        comp = comparison(path, text, full=False)
                        e.update(path=path, file_access='read', display_name=Path(path).name,
                                 read_range={'kind': 'partial', 'label': 'Grep 筛选', 'selectors': [{'method': 'grep'}]},
                                 comparison_status=comp['status'], comparison=comp)
                if isinstance(result, dict):
                    image_ids = [b.get('source', {}).get('data_ref') for b in blocks(result.get('content', [])) if b.get('type') == 'image']
                    e['image_ids'] = [i for i in image_ids if i]
                    if e['image_ids']:
                        e.update(operation='read', operation_label=OPERATIONS['read'])
        # Results whose calls preceded an explicitly selected main-agent range
        # are before_range evidence, not new events.
        seen_humans = set()
        for item in self.items:
            group, kind = item['group'], item.get('kind')
            queued = item.get('attachment_type') == 'queued_command'
            op = 'user' if queued else 'reminder' if group == 'reminders' else 'return' if kind == 'handback' else 'user' if group == 'upstream' and not self.node['agent_id'] and kind != 'dispatch' else None
            if not op:
                continue
            ref = item.get('display_ref')
            text = content_text(self.doc.resolve(ref)) if ref else ''
            if op == 'user' and not queued and re.match(r'\s*<(?:system-reminder|agent-message|task-notification)[>\s]', text):
                op = 'reminder'
            number = item['first_request'] or self.node['range']['start']
            skill = re.match(r'Base directory for this skill: (\S+)\n', text) if op == 'user' else None
            if skill:
                # The Skill tool injects SKILL.md as a meta user message; it is a read of that file.
                path = path_of(os.path.join(skill[1], 'SKILL.md'), self.node['cwd'])
                body = re.sub(r'\n+ARGUMENTS: .*\Z', '', text[skill.end():], flags=re.S)
                comp = skill_comparison(path, body)
                e = self.make('item/' + digest(item['id'])[:20], 'read', number)
                e.update(method='Skill', display_name='SKILL.md', path=path, file_access='read',
                         read_range={'kind': 'full', 'label': '全文（Skill 工具加载，不含开头的 frontmatter）', 'selectors': []},
                         comparison_status=comp['status'], comparison=comp, content_ref=self.doc.ref(text),
                         item_ids=[item['id']], raw_refs=[ref] if ref else [], characters=len(text),
                         timestamp=item.get('timestamp') or e['timestamp'])
                continue
            if op == 'user':
                if text in seen_humans:
                    continue
                seen_humans.add(text)
            e = self.make('item/' + digest(item['id'])[:20], op, number)
            e.update(method=OPERATIONS[op], display_name='用户消息（运行中插入）' if queued else '用户消息' if op == 'user' else '返回' if op == 'return' else '系统提醒' if item['label'] in ('中途提醒', '你的消息') else item['label'],
                     content_ref=self.doc.ref(text), item_ids=[item['id']], raw_refs=[ref] if ref else [], characters=len(text),
                     timestamp=item.get('timestamp') or e['timestamp'], ends_segment='return' if op == 'return' else None)
        # Model text and non-empty thinking are outputs; empty thinking shells are not shown.
        for rid in self.node['request_ids']:
            req = self.d['requests'][rid]
            if not req.get('response_ref'):
                continue
            message = self.doc.resolve(req['response_ref'])
            for i, b in enumerate(blocks(message.get('content', []))):
                kind = b.get('type')
                text = b.get('text') if kind == 'text' else b.get('thinking') if kind == 'thinking' else None
                if not isinstance(text, str) or not text.strip():
                    continue
                op = 'reply' if kind == 'text' else 'think'
                first = text.strip().splitlines()[0].strip()
                e = self.make('%s/%d/%d' % (op, req['number'], i), op, req['number'])
                e.update(method='模型回复' if op == 'reply' else '思考',
                         display_name=first[:40] + ('…' if len(first) > 40 or '\n' in text.strip() else ''),
                         content_ref=dict(req['response_ref'], pointer='/content/%d/%s' % (i, 'text' if op == 'reply' else 'thinking')),
                         characters=len(text))
        expanded = []
        for e in self.events:
            e['visible_characters'] = len(content_text(self.doc.resolve(e['content_ref']))) if e['content_ref'] else 0
            if len(e['image_ids']) > 1:
                for i, image_id in enumerate(e['image_ids']):
                    child = dict(e, id=e['id'] + '/image/' + str(i), image_ids=[image_id], image_index=i)
                    if i:
                        child.update(characters=0, visible_characters=0, content_ref=self.doc.ref(''), written_files=[])
                    expanded.append(child)
            else:
                expanded.append(e)
        self.events = expanded
        for e in self.events:
            tool_key = e['id'].split('/event/', 1)[1].split('/', 1)[0]
            e['tool_use_id'] = tool_key if tool_key in self.calls else None
            if e.get('path'):
                e['directory_hint'] = display_path(str(Path(e['path']).parent), self.node['cwd']).rstrip('/') + '/'
            e['is_focus'] = e.get('path') in self.doc.focus
        # Preserve first appearance within a request; result reads precede writes.
        def key(e):
            rank = (-1 if e['operation'] == 'user' else 2 if e['ends_segment'] else 1 if e['operation'] in ('write', 'edit')
                    else 0.5 if e['operation'] in ('reply', 'think') else 0)
            return e['request_number'], rank, e['timestamp'] or '', self.events.index(e)
        self.events = sorted(self.events, key=key)
        for e in self.events:
            # Outputs: document writes, the scoped output, spawn, return, model text and thinking.
            e['is_output'] = bool(e['ends_segment']) or e['operation'] in ('reply', 'think')
            e['is_code'] = is_code(e)
            self.d['events'][e['id']] = e
        self.node['event_ids'] = [e['id'] for e in self.events]
        segmented = bool(self.node['agent_id']) or any(e['ends_segment'] == 'write' for e in self.events)
        self.node['timeline_mode'] = 'segments' if segmented else 'events'
        self.node['leading_event_ids'] = []
        if segmented and not self.node['agent_id']:
            for e in self.events:
                if e['operation'] != 'user':
                    break
                self.node['leading_event_ids'].append(e['id'])
        segment_events(self.d, self.node)
        self.node['trace_rows'] = trace_rows(self.d, self.node)
        self.node['timeline'] = ([dict(kind='event', id=eid) for eid in self.node['leading_event_ids']] +
                                [dict(kind='segment', id=sid) for sid in self.node['segment_ids']] if segmented
                                 else [dict(kind='event', id=e['id']) for e in self.events])


def initial_context(doc, node):
    d = doc.data
    first = d['requests'][node['request_ids'][0]]
    categories = {}
    child = bool(node.get('agent_id'))
    groups = [('system', 'system'), ('tools', 'tools'), ('injected', 'automatic')]
    groups.append(('task', 'upstream') if child else ('history', 'before_range'))
    history_refs = defaultdict(list)
    if not child:
        # A manually narrowed range can start mid-task, after the latest user
        # message. Its earlier replies/results need initial-context entries
        # even when v1 did not place them in the before_range group.
        live_refs = {json.dumps(ref, sort_keys=True) for eid in node.get('event_ids', [])
                     for ref in d['events'][eid]['raw_refs']}
        for own in first.get('ownership', []):
            item = d['items'][own['owner_id']]
            if item['group'] in ('system', 'tools', 'automatic', 'upstream'):
                continue
            if json.dumps(own['raw_ref'], sort_keys=True) not in live_refs:
                history_refs[item['id']].append(own['raw_ref'])
    for key, group in groups:
        ids = [iid for iid in node['groups'][group] if iid in first['context_item_ids'] or (child and group == 'automatic')]
        if key == 'history':
            ids = list(history_refs)
        if key == 'history' and not ids:
            continue
        entries = [dict(item_id=iid, characters=d['items'][iid]['characters'], content_ref=d['items'][iid].get('display_ref'),
                        first_request=d['items'][iid]['first_request'], available_in_first_request=iid in first['context_item_ids']) for iid in ids]
        if key == 'history':
            for entry in entries:
                refs = history_refs[entry['item_id']]
                values = [doc.resolve(ref) for ref in refs]
                # Reuse refs instead of re-interning values whose images have
                # already been replaced with data_ref by Document.source().
                entry.update(content_ref=None, content_refs=refs,
                             characters=sum(len(json.dumps(v, ensure_ascii=False)) if isinstance(v, dict) and
                                            v.get('type') in ('tool_use', 'tool_addition') else len(content_text(v)) for v in values))
        if group == 'tools':
            for entry in entries:
                tool = doc.resolve(entry['content_ref'])
                entry.update(name=tool.get('name'), description_ref=doc.ref(tool.get('description', '')))
        categories[key] = dict(label='范围开始前的对话' if key == 'history' else CATEGORIES[key], item_ids=ids, entries=entries, characters=sum(x['characters'] for x in entries))
    node['initial_context'] = dict(request_id=first['id'], categories=categories, characters=sum(x['characters'] for x in categories.values()))


def compositions(doc, node):
    d = doc.data
    item_events = defaultdict(list)
    for eid in node['event_ids']:
        for iid in d['events'][eid]['item_ids']:
            item_events[iid].append(d['events'][eid])
    for sid in node['segment_ids']:
        segment = d['segments'][sid]
        req = d['requests'][segment['context_request_id']]
        categories = {k: dict(label=v, characters=0, item_ids=[], event_ids=[], parts=[]) for k, v in CATEGORIES.items()}
        for own in req.get('ownership', []):
            item = d['items'][own['owner_id']]
            group = item['group']
            category = {'system': 'system', 'tools': 'tools', 'automatic': 'injected', 'upstream': 'task',
                        'requests': 'model', 'reminders': 'reminders', 'before_range': 'previous'}.get(group)
            ref = own['raw_ref']
            value = doc.resolve(ref)
            linked = [e for iid in [own['owner_id']] + own['related_ids'] for e in item_events[iid]
                      if e['request_number'] <= req['number'] and (any(r['source_id'] == ref['source_id'] and
                         (r.get('pointer', '') == ref.get('pointer', '') or group not in ('files', 'commands')) for r in e['raw_refs'])
                         or (isinstance(value, dict) and value.get('type') == 'tool_result' and value.get('tool_use_id') == e.get('tool_use_id')))]
            if any(e['operation'] == 'reminder' for e in linked):
                category = 'reminders'
            elif any(e['operation'] == 'user' for e in linked):
                category = 'task'
            if category is None:
                category = 'current' if any(e.get('segment_id') == sid for e in linked) else 'previous'
            structured = isinstance(value, dict) and (('input_schema' in value and group == 'tools') or value.get('type') in ('tool_use', 'tool_addition'))
            chars = len(json.dumps(value, ensure_ascii=False)) if structured else len(content_text(value))
            cat = categories[category]
            cat['characters'] += chars
            cat['item_ids'].extend([own['owner_id']] + own['related_ids'])
            cat['event_ids'].extend(e['id'] for e in linked)
            cat['parts'].append(dict(raw_ref=ref, characters=chars, item_id=own['owner_id'], event_ids=[e['id'] for e in linked]))
        for cat in categories.values():
            cat['item_ids'] = list(dict.fromkeys(cat['item_ids']))
            cat['event_ids'] = list(dict.fromkeys(cat['event_ids']))
        cid = sid + '/context'
        d['context_compositions'][cid] = dict(id=cid, request_id=req['id'], node_id=node['id'], segment_id=sid,
                                             characters=sum(c['characters'] for c in categories.values()), categories=categories)
        segment['context_composition_id'] = cid


def overview(doc, node):
    d = doc.data
    events = [d['events'][eid] for eid in node['event_ids']]
    reads, writes = {}, {}
    for e in events:
        if e.get('read_id') or e.get('file_access') == 'read':
            row = reads.setdefault(e['path'], dict(path=e['path'], display_path=display_path(e['path'], node['cwd']), count=0,
                                                 first_request=e['request_number'], characters=0, event_ids=[]))
            row['count'] += 1
            row['characters'] += e['characters']
            row['event_ids'].append(e['id'])
        for w in e['written_files']:
            row = writes.setdefault(w['path'], dict(path=w['path'], display_path=display_path(w['path'], node['cwd']), count=0, event_ids=[], write_ids=[]))
            row['count'] += 1
            row['event_ids'].append(e['id'])
            row['write_ids'].append(w['write_id'])
    node['overview'] = dict(request_count=len(node['request_ids']), start=node['start'], end=node['end'], context_tokens=node['context_tokens'],
                            operation_counts=event_counts(events), image_count=sum(bool(e['image_ids']) for e in events),
                            read_files=list(reads.values()), written_files=list(writes.values()))
    if doc.focus:
        node['overview']['focus_coverage'] = [dict(path=p, display_path=display_path(p, node['cwd']),
                                                 event_ids=[e['id'] for e in events if e.get('path') == p or any(w['path'] == p for w in e['written_files'])],
                                                 appeared=p in reads or p in writes) for p in doc.focus]


def upgrade(doc):
    d = doc.data
    d.update(schema_version='2.0', events={}, segments={}, context_compositions={}, file_references=[], files={},
             operation_labels=OPERATIONS, context_category_labels=CATEGORIES)
    for node in d['nodes']:
        ChainBuilder(doc, node).build()
        initial_context(doc, node)
        compositions(doc, node)
        overview(doc, node)
    read_events = {e['read_id']: e['id'] for e in d['events'].values() if e.get('read_id')}
    write_events = {w['write_id']: e['id'] for e in d['events'].values() for w in e.get('written_files', [])}
    for edge in d['edges']:
        if edge['kind'] == 'file_flow':
            edge.update(source_node_id=edge['producer_node_id'], target_node_id=edge['consumer_node_id'],
                        source_event_id=write_events.get(edge['version_write_id']), target_event_id=read_events.get(edge['read_id']))
        else:
            edge.update(source_node_id=edge['parent_node_id'], target_node_id=edge['child_node_id'],
                        source_event_id=next((e['id'] for e in d['events'].values() if e.get('child_node_id') == edge['child_node_id']), None))
    d['trace_overview'] = dict(node_ids=[n['id'] for n in d['nodes']], edge_ids=[e['id'] for e in d['edges']])
    from file_index import build_files
    build_files(doc)


def render_tree(data, display_range):
    scope = data['scope']
    name = ' / '.join(Path(scope['from_output']).parent.parts[-2:]) if scope.get('from_output') else '追踪'
    lines = ['%s · %s（北京时间）' % (name, display_range(scope['start'], scope['end']))]
    nodes = {n['id']: n for n in data['nodes']}
    emitted = set()

    def visible(ids):
        return [i for i in ids or [] if data['events'][i]['operation'] not in ('reply', 'think')]

    def event(eid, indent):
        e = data['events'][eid]
        count = ' · %s 字符' % format(e['characters'], ',') if e['characters'] else ''
        lines.append(indent + '第 %d 轮  %s %s%s' % (e['request_number'], e['operation_label'], e['display_name'], count))

    def header(ops, ends):
        parts, seen = [], set()
        for eid in ends:
            e = data['events'][eid]
            key = e.get('path') or eid
            if key in seen:
                continue
            seen.add(key)
            name = '' if e['display_name'] == e['operation_label'] else e['display_name']
            if parts and parts[-1][0] == e['operation_label']:
                parts[-1][1].append(name)
            else:
                parts.append((e['operation_label'], [name]))
        text = '，'.join((label + ' ' + '、'.join(n for n in names if n)).strip() for label, names in parts)
        return ('%d 次操作 → %s' % (ops, text)) if ops and text else text or '%d 次操作' % ops

    def emit(node, indent=''):
        """和页面同一结构：Agent → 上下文 → 段「N 次操作 → 写入 X」→ 每次操作（行首是第几轮）。"""
        if node['id'] in emitted:
            return
        emitted.add(node['id'])
        lines.append(indent + ('子 Agent ' + node['title'] if node['agent_id'] else '主 Agent'))
        cats = (node.get('initial_context') or {}).get('categories') or {}
        if cats:
            lines.append(indent + '  上下文 · ' + ' · '.join('%s %d' % (c['label'], len(c.get('item_ids', []))) for c in cats.values()))
        segments = [data['segments'][sid] for sid in node.get('segment_ids', []) if sid in data['segments']]
        if not any(sg['end_kind'] != 'open' for sg in segments):
            for eid in visible(node['event_ids']):
                event(eid, indent + '  ')
            return
        for eid in visible(node.get('leading_event_ids')):
            event(eid, indent + '  ')
        merged = []  # 只隔着模型说话的两次写入并成一段，和页面一致
        for sg in segments:
            ops, ends = visible(sg['event_ids']), visible(sg['ending_event_ids'])
            if merged and not ops and sg['end_kind'] == 'write' and merged[-1][0]['end_kind'] == 'write':
                merged[-1][2].extend(ends)
            else:
                merged.append((sg, ops, ends))
        for sg, ops, ends in merged:
            lines.append(indent + '  ' + header(len(ops), ends))
            spawn = data['events'][ends[0]] if sg['end_kind'] == 'spawn' and len(ends) == 1 else None
            for eid in ops + ([] if spawn else ends):
                event(eid, indent + '    ')
            if spawn and spawn.get('child_node_id') in nodes:
                emit(nodes[spawn['child_node_id']], indent + '    ')
    for node in data['nodes']:
        if not node.get('parent_id'):
            emit(node)
    for node in data['nodes']:
        emit(node)
    for edge in data['edges']:
        if edge['kind'] == 'file_flow':
            def who(request_id):
                node = nodes.get(request_id.split('/request/')[0])
                return (node['title'] if node and node['agent_id'] else '主 Agent') + ' 第 ' + request_id.rsplit('/', 1)[-1] + ' 轮'
            lines.append('文件流转 %s · %s写入 → %s读取' % (Path(edge['path']).name, who(edge['version_request_id']), who(edge['read_request_id'])))
    return '\n'.join(lines)
