"""File/directory mentions and bounded, local file sidebar snapshots for v2."""
import os
import re
from collections import defaultdict
from pathlib import Path

from provenance import timestamp_seconds
from records import digest

MAX_TEXT_BYTES = 1024 * 1024
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.avif', '.bmp', '.tif', '.tiff', '.ico'}
# Punctuation surrounding Markdown/code/Chinese quotations is not part of a path.
TOKENS = re.compile(r'''[^\s`"'<>\[\](){}，。；：！？、「」『』“”‘’|=*]+''')
FILE_END = re.compile(r'\.[A-Za-z][A-Za-z0-9_-]{0,11}$')


class ReferenceResolver:
    def __init__(self, known_paths):
        self.known = set(known_paths)
        directories = set()
        for path in self.known:
            directories.update(str(p) for p in Path(path).parents)
            if Path(path).is_dir():
                directories.add(path)
        self.by_name = {'file': defaultdict(list), 'dir': defaultdict(list)}
        for kind, paths in (('file', self.known - directories), ('dir', directories)):
            for path in sorted(paths):
                self.by_name[kind][Path(path).name].append(path)
        self.trees = {}
        self.cache = {}

    def available(self, path, kind):
        try:
            return Path(path).is_dir() if kind == 'dir' else (path in self.known and not Path(path).is_dir()) or Path(path).is_file()
        except OSError:
            return False

    def resolve(self, token, source_path=None, cwd=None, kind='file'):
        key = (token, source_path, cwd, kind)
        if key not in self.cache:
            self.cache[key] = self._resolve(token, source_path, cwd, kind)
        return self.cache[key]

    def _resolve(self, token, source_path, cwd, kind):
        if '://' in token or '\x00' in token or any(c in token for c in ('$','*','?')):
            return None
        if token.startswith(('/', '~/')):
            path = os.path.realpath(os.path.expanduser(token))
            return (path, 1) if self.available(path, kind) else None
        for level, directory in ((2, str(Path(source_path).parent) if source_path else None), (3, cwd)):
            if directory:
                path = os.path.realpath(os.path.join(directory, token))
                if self.available(path, kind):
                    return path, level
        suffix = token.removeprefix('./').rstrip('/')
        matches = [p for p in self.by_name[kind][Path(suffix).name] if p.endswith('/' + suffix) and self.available(p, kind)]
        if matches:
            return (matches[0], 4) if len(matches) == 1 else None
        if source_path:
            directory = str(Path(source_path).parent)
            if directory not in self.trees:
                # A single scandir traversal per source directory, no shell or
                # recursive symlink traversal; candidates are never executed.
                paths = {'file': defaultdict(list), 'dir': defaultdict(list)}
                for root, dirs, names in os.walk(directory):
                    for name in dirs:
                        paths['dir'][name].append(os.path.realpath(os.path.join(root, name)))
                    dirs[:] = [d for d in dirs if not Path(root, d).is_symlink()]
                    for name in names:
                        paths['file'][name].append(os.path.realpath(os.path.join(root, name)))
                self.trees[directory] = paths
            matches = sorted(set(p for p in self.trees[directory][kind][Path(suffix).name] if p.endswith('/' + suffix) and self.available(p, kind)))
            if len(matches) == 1:
                return matches[0], 5
        return None

    def scan(self, text, source_path=None, cwd=None):
        candidates = [(m.start(), m.end(), m[0]) for m in TOKENS.finditer(text)]
        # Quoted/code paths can contain spaces. The ordinary tokenizer still
        # handles multiple filenames in one code span.
        for m in re.finditer(r'[`"\'「“]([^\n`"\'」”]+)[`"\'」”]', text):
            if ' ' in m[1]:
                candidates.append((m.start(1), m.end(1), m[1]))
        found = []
        for start, end, token in sorted(candidates, key=lambda c: (c[0], -(c[1] - c[0]))):
            token = token.rstrip('.,;:!')
            token = re.sub(r':\d+(?:-\d+)?$', '', token)
            if any(start < row[1] and row[0] < start + len(token) for row in found):
                continue
            kinds = ['file'] if FILE_END.search(token) else []
            if token.startswith(('/', '~/')) or token.endswith('/'):
                kinds.append('dir')
            for kind in kinds:
                resolved = self.resolve(token, source_path, cwd, kind)
                if resolved:
                    found.append((start, start + len(token), resolved[0], resolved[1], kind))
                    break
        return found


def line_ranges(event, line_count):
    """Map selectors to source lines only when the mapping is deterministic."""
    if event.get('output_truncated') or event.get('shared_with') or not event.get('read_id') or event.get('image_ids'):
        return []
    coverage = event.get('read_range') or {}
    selectors = coverage.get('selectors', [])
    if any(s.get('method') in ('grep', 'rg', 'awk') or s.get('bytes') is not None for s in selectors):
        return []
    if coverage.get('kind') == 'full':
        return [dict(start=1, end=line_count, kind='full')] if line_count else []
    lines = list(range(1, line_count + 1))
    if not selectors:
        return []
    for selector in selectors:
        method = selector.get('method')
        if method == 'Read':
            offset = max(1, int(selector.get('offset') or 1)) - 1
            limit = selector.get('limit')
            lines = lines[offset:offset + int(limit)] if limit is not None else lines[offset:]
        elif method in ('head', 'tail'):
            try:
                raw = str(selector.get('lines') or '10')
                n = int(raw)
            except ValueError:
                return []
            if method == 'head':
                lines = lines[:n]
            elif raw.startswith('+'):
                lines = lines[max(n - 1, 0):]
            else:
                lines = lines[-abs(n):] if n else []
        elif method == 'sed':
            ranges = selector.get('ranges')
            if not ranges:
                return []
            lines = [line for i, line in enumerate(lines, 1) if any(a <= i <= b for a, b in ranges)]
        else:
            return []
    result = []
    for line in lines:
        if result and line == result[-1]['end'] + 1:
            result[-1]['end'] = line
        else:
            result.append(dict(start=line, end=line, kind='lines'))
    return result


def build_files(doc):
    from chain import content_text, display_path
    d = doc.data
    nodes = {n['id']: n for n in d['nodes']}
    file_events = defaultdict(list)
    for e in d['events'].values():
        if e['kind'] in ('group', 'inputs'):
            continue
        paths = ([e['path']] if e.get('read_id') or e.get('file_access') == 'read' else []) + [w['path'] for w in e['written_files']]
        for path in dict.fromkeys(paths):
            file_events[path].append(e)
    resolver = ReferenceResolver(file_events)
    # Display texts, rather than JSON wrappers or model thinking. The same raw
    # source can appear in more than one file context with different resolution.
    texts = {}

    def add(ref, owner_id, node_id, path=None):
        if not ref:
            return
        text = content_text(doc.resolve(ref))
        if not text:
            return
        normalized = doc.ref(text)
        key = (normalized['source_id'], path, node_id)
        entry = texts.setdefault(key, dict(text=text, ref=normalized, owners=[], node_id=node_id, path=path))
        if owner_id not in entry['owners']:
            entry['owners'].append(owner_id)

    for e in d['events'].values():
        if e['kind'] in ('group', 'inputs'):
            continue
        add(e['content_ref'], e['id'], e['node_id'], e.get('path'))
        for w in e['written_files']:
            for field in ('content_ref', 'before_ref', 'after_ref'):
                add(w.get(field), e['id'], e['node_id'], w['path'])
        # Command / parameters are visible in event details as well.
        if e.get('call_ref'):
            call = doc.resolve(e['call_ref'])
            inp = call.get('input', {})
            for key in ('command', 'prompt', 'url', 'pattern'):
                if isinstance(inp.get(key), str):
                    add(doc.ref(inp[key]), e['id'], e['node_id'])
    for node in d['nodes']:
        for group in ('system', 'tools', 'automatic', 'upstream', 'reminders'):
            for iid in node['groups'][group]:
                item = d['items'][iid]
                if group == 'tools':
                    value = doc.resolve(item['display_ref'])
                    add(doc.ref(value.get('description', '')), iid, node['id'])
                else:
                    add(item.get('display_ref'), iid, node['id'], item.get('path'))
    for entry in texts.values():
        for start, end, path, level, kind in resolver.scan(entry['text'], entry['path'], nodes[entry['node_id']]['cwd']):
            rid = 'file-ref:' + digest((entry['ref'], start, end, path, entry['node_id'], entry['path']))[:24]
            d['file_references'].append(dict(id=rid, source_id=entry['ref']['source_id'], text_ref=entry['ref'],
                                             start=start, end=end, path=path, kind=kind, resolution_level=level,
                                             source_path=entry['path'], node_id=entry['node_id'], owner_ids=entry['owners']))
            if kind == 'file':
                file_events.setdefault(path, [])
    reference_ids = defaultdict(list)
    for ref in d['file_references']:
        reference_ids[ref['path']].append(ref['id'])
    for path, events in sorted(file_events.items()):
        p = Path(path)
        if p.is_dir():
            continue
        try:
            stat = p.stat() if p.is_file() else None
        except OSError:
            stat = None
        events.sort(key=lambda e: (e['timestamp'] or '', e['request_number']))
        reads = [e for e in events if (e.get('read_id') or e.get('file_access') == 'read') and e.get('path') == path and not e.get('failed')]
        image = p.suffix.lower() in IMAGE_EXTENSIONS or any(e['image_ids'] for e in reads)
        last = reads[-1] if reads else None
        status = last['comparison_status'] if last else 'unavailable'
        basis = last.get('comparison', {}).get('basis') if last else '没有历史读取证据'
        # A matching excerpt does not prove the rest of a file unchanged.
        if stat and last and last['read_range']['kind'] != 'full':
            end = nodes[last['node_id']]['end']
            if end and stat.st_mtime > timestamp_seconds(end):
                status, basis = 'different', '文件修改时间晚于代理结束时间'
        # A later successful full Write is a more recent version than a read.
        writes = [(e, w) for e in events for w in e['written_files'] if w['path'] == path and not w['failed']]
        if stat and writes and (not last or (writes[-1][0]['timestamp'] or '') >= (last['timestamp'] or '')):
            e, w = writes[-1]
            if w.get('content_ref') and w.get('content_kind') != 'append' and stat.st_size <= MAX_TEXT_BYTES and not image:
                try:
                    same = p.read_text(encoding='utf-8').rstrip('\n') == doc.resolve(w['content_ref']).rstrip('\n')
                    status, basis = ('same' if same else 'different'), '最后一次写入全文比较'
                except (OSError, UnicodeError):
                    pass
        if not stat:
            status, basis = 'missing', '文件不在磁盘'
        row = dict(id='file:' + digest(path)[:24], path=path, display_path=display_path(path), exists=bool(stat),
                   type='image' if image else 'text', bytes=stat.st_size if stat else None,
                   event_ids=[e['id'] for e in events], reference_ids=reference_ids[path],
                   comparison_status=status, comparison_basis=basis, content_ref=None, content_version=None,
                   last_read_event_id=last['id'] if last else None, last_read_request_id=last['request_id'] if last else None,
                   last_read_request_number=last['request_number'] if last else None,
                   read_ranges=[], image_ids=list(dict.fromkeys(i for e in reads for i in e['image_ids'])), omitted_reason=None)
        if image:
            row['content_version'] = 'recorded' if reads else 'path_only'
        elif status in ('different', 'missing') and last:
            # This is a reference to already retained model-visible content;
            # the 1 MB cap concerns new disk snapshots, not recorded evidence.
            row.update(content_ref=last['content_ref'], content_version='last_read')
        elif status == 'different':
            row['omitted_reason'] = 'no_recorded_read'
        elif stat and stat.st_size <= MAX_TEXT_BYTES:
            try:
                with p.open('rb') as f:
                    raw = f.read(MAX_TEXT_BYTES + 1)
                if len(raw) > MAX_TEXT_BYTES:
                    row['omitted_reason'] = 'over_1mb'
                elif b'\x00' in raw:
                    row['omitted_reason'] = 'not_text'
                else:
                    text = raw.decode('utf-8')
                    row.update(content_ref=doc.ref(text), content_version='current')
                    row['read_ranges'] = [dict(r, event_id=e['id'], request_id=e['request_id']) for e in reads
                                          for r in line_ranges(e, len(text.splitlines()))]
            except (OSError, UnicodeError):
                row['omitted_reason'] = 'not_utf8_or_unreadable'
        else:
            row['omitted_reason'] = 'over_1mb' if stat else 'missing'
        d['files'][path] = row
    # Direct IDs for click targets; sources themselves remain content-addressed.
    for ref in d['file_references']:
        ref['file_id'] = d['files'][ref['path']]['id'] if ref['kind'] == 'file' else None
        for owner in ref['owner_ids']:
            target = d['events'].get(owner) or d['items'].get(owner)
            if target is not None:
                target.setdefault('file_reference_ids', []).append(ref['id'])
