"""公开这个例子前用的脱敏脚本：trace 数据 JSON → 可以公开的 JSON。

用法：
  python3 -I redact.py data.json public.json \
      --keep-file-prefix <只保留这个前缀下的文件引用> \
      --replace <原文>=<替换成> ...

做三件事：
1. 初始上下文里这几类内容整段换成「【已省略：<名字>，约 N 字符】」：系统提示词，
   以及注入内容里的全局 CLAUDE.md、记忆、账号、skill 列表、MCP 说明、延后加载的工具。
   同一段文字在每一轮请求里都会重复出现，所以按原文在整份数据里替换。
2. 家目录、临时目录这类本机路径换成通用写法（--replace 可以再加）。
3. 只保留 --keep-file-prefix 下的文件引用；其余文件连同嵌入的全文一起删掉。
替换会改变字符串长度，所有指向原文的 start / end 偏移都跟着重算。
"""
import argparse
import json
import re
from pathlib import Path

REDACT_LABELS = ('CLAUDE.md', 'MEMORY.md', '记忆', '账号', 'skill 列表', 'MCP 说明', '延后加载的工具')


def resolve(sources, ref):
    obj = sources[ref['source_id']]
    for part in [p for p in ref.get('pointer', '').split('/')[1:]]:
        obj = obj[int(part)] if isinstance(obj, list) else obj[part]
    return obj


def texts_in(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for v in value:
            yield from texts_in(v)
    elif isinstance(value, dict):
        for k, v in value.items():
            if k == 'text' or isinstance(v, (list, dict)):
                yield from texts_in(v)


def secrets(data):
    found = {}
    for node in data['nodes']:
        for key, category in (node.get('initial_context') or {}).get('categories', {}).items():
            for entry in category['entries']:
                item = data['items'][entry['item_id']]
                label = item.get('label') or category['label']
                if key != 'system' and not any(word in label for word in REDACT_LABELS):
                    continue
                value = resolve(data['sources'], entry['content_ref'])
                if isinstance(value, str) and 'start' in entry['content_ref']:
                    value = value[entry['content_ref']['start']:entry['content_ref']['end']]
                for text in texts_in(value):
                    if len(text) >= 40:
                        found.setdefault(text, label if key != 'system' else '系统提示词')
    return found


def build_pattern(found, replaces):
    keys = sorted(found, key=len, reverse=True) + sorted(replaces, key=len, reverse=True)
    return re.compile('|'.join(re.escape(k) for k in keys)) if keys else None


def rewrite(text, pattern, found, replaces):
    spans, out, last = [], [], 0
    for m in pattern.finditer(text):
        token = m.group(0)
        new = '【已省略：%s，约 %s 字符】' % (found[token], format(len(token), ',')) if token in found else replaces[token]
        out.append(text[last:m.start()]); out.append(new); last = m.end()
        spans.append((m.start(), m.end(), len(new), token in found))
    out.append(text[last:])
    return ''.join(out), spans


def walk_sources(value, pointer, sid, pattern, found, replaces, remap):
    if isinstance(value, str):
        new, spans = rewrite(value, pattern, found, replaces)
        if spans:
            remap[(sid, pointer)] = spans
        return new
    if isinstance(value, list):
        return [walk_sources(v, '%s/%d' % (pointer, i), sid, pattern, found, replaces, remap) for i, v in enumerate(value)]
    if isinstance(value, dict):
        return {k: walk_sources(v, '%s/%s' % (pointer, k), sid, pattern, found, replaces, remap) for k, v in value.items()}
    return value


def move(position, spans, is_end):
    delta = 0
    for start, end, new_len, secret in spans:
        if position <= start:
            break
        if position >= end:
            delta += new_len - (end - start)
            continue
        return None if secret else start + delta + (new_len if is_end else 0)
    return position + delta


def fix_offsets(value, remap, dropped):
    if isinstance(value, list):
        return [x for x in (fix_offsets(v, remap, dropped) for v in value) if x is not dropped]
    if not isinstance(value, dict):
        return value
    value = {k: fix_offsets(v, remap, dropped) for k, v in value.items()}
    ref = value.get('text_ref') if isinstance(value.get('text_ref'), dict) else value
    if 'start' in value and 'end' in value and isinstance(ref.get('source_id'), str) and 'pointer' in ref:
        spans = remap.get((ref['source_id'], ref['pointer']))
        if spans and isinstance(value['start'], int):
            start, end = move(value['start'], spans, False), move(value['end'], spans, True)
            if start is None or end is None:
                if value.get('id', '').startswith('file-ref:'):
                    return dropped
                start = start if start is not None else end
            value['start'], value['end'] = start, end if end is not None else start
    return value


def map_strings(value, replaces, pattern):
    if isinstance(value, str):
        return pattern.sub(lambda m: replaces[m.group(0)], value) if pattern else value
    if isinstance(value, list):
        return [map_strings(v, replaces, pattern) for v in value]
    if isinstance(value, dict):
        return {map_strings(k, replaces, pattern): map_strings(v, replaces, pattern) for k, v in value.items()}
    return value


def source_ids(value, acc):
    if isinstance(value, dict):
        for k, v in value.items():
            if k == 'source_id' and isinstance(v, str):
                acc.add(v)
            else:
                source_ids(v, acc)
    elif isinstance(value, list):
        for v in value:
            source_ids(v, acc)
    return acc


def redact(data, keep_prefixes, extra):
    home = str(Path.home())
    user = Path.home().name
    replaces = dict(extra)
    for m in set(re.findall(r'/private/tmp/claude-\d+/[^/\s"]+/[0-9a-f-]{36}/scratchpad', json.dumps(data, ensure_ascii=False))):
        replaces[m] = '/tmp/scratchpad'
    for m in set(re.findall(r'-private-tmp-claude-\d+--Users-%s[^/\s"]*?-scratchpad' % re.escape(user), json.dumps(data, ensure_ascii=False))):
        replaces[m] = '-tmp-scratchpad'
    replaces.setdefault(home, '~')
    replaces.setdefault('-Users-%s' % user, '-Users-me')
    found = secrets(data)
    pattern = build_pattern(found, replaces)
    remap = {}
    sources = {sid: walk_sources(src, '', sid, pattern, found, replaces, remap) for sid, src in data['sources'].items()}
    rest = {k: v for k, v in data.items() if k != 'sources'}
    dropped = object()
    rest = fix_offsets(rest, remap, dropped)
    path_pattern = build_pattern({}, replaces)
    rest = map_strings(rest, replaces, path_pattern)
    keep = lambda path: any(path.startswith(p) for p in keep_prefixes)
    rest['files'] = {p: f for p, f in rest['files'].items() if keep(p)}
    rest['file_references'] = [r for r in rest['file_references'] if keep(r.get('path') or '')]
    live = source_ids(rest, set())
    rest['sources'] = {sid: src for sid, src in sources.items() if sid in live}
    return rest, found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('dst')
    ap.add_argument('--keep-file-prefix', action='append', default=[])
    ap.add_argument('--replace', action='append', default=[])
    a = ap.parse_args()
    extra = dict(x.split('=', 1) for x in a.replace)
    data, found = redact(json.load(open(a.src, encoding='utf-8')), a.keep_file_prefix, extra)
    json.dump(data, open(a.dst, 'w', encoding='utf-8'), ensure_ascii=False)
    labels = {}
    for text, label in found.items():
        labels[label] = labels.get(label, 0) + len(text)
    for label, n in sorted(labels.items()):
        print('已省略 %s：%s 字符' % (label, format(n, ',')))


if __name__ == '__main__':
    main()
