#!/usr/bin/env python3
"""Read-only Feishu XML comparison. Checks structure, not semantics or pixels."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


def read_document(path):
    raw = Path(path).read_text(encoding='utf-8')
    revision = None
    if raw.lstrip().startswith('{'):
        obj = json.loads(raw)
        if obj.get('ok') is False:
            raise ValueError(f'fetch failed: {path}')
        doc = obj.get('data', {}).get('document', obj.get('document', obj))
        raw = doc['content']
        revision = doc.get('revision_id')
    if '<!DOCTYPE' in raw.upper() or '<!ENTITY' in raw.upper():
        raise ValueError('XML entity declarations are not accepted')
    root = ET.fromstring('<audit-root>' + raw + '</audit-root>')
    if len(root) == 1 and root[0].tag in ('doc', 'document', 'audit-root'):
        root = root[0]
    return root, revision


def text(node):
    return ''.join(node.itertext()).strip()


def normalized(node):
    return (node.tag, sorted((k, v) for k, v in node.attrib.items()
                            if k != 'seq-marker'), node.text or '',
            [(normalized(c), c.tail or '') for c in node])


def block_map(root):
    ids = [e.get('id') for e in root.iter() if e.get('id')]
    duplicate = [key for key, count in Counter(ids).items() if count > 1]
    if duplicate:
        raise ValueError('duplicate block IDs: ' + ', '.join(duplicate))
    return {e.get('id'): e for e in root.iter() if e.get('id')}


def resource_list(root):
    return [{'tag': e.tag, 'id': e.get('id'), 'token': e.get('token'),
             'src': e.get('src'), 'name': e.get('name'), 'size': e.get('size')}
            for e in root.iter() if e.tag in ('whiteboard', 'img', 'source')]


def audit(before, after, allowed):
    old, new = block_map(before), block_map(after)
    unknown = sorted(set(allowed) - set(old))
    if unknown:
        raise ValueError('allowed IDs not in baseline: ' + ', '.join(unknown))
    permitted = set(allowed)
    for key in allowed:
        permitted.update(e.get('id') for e in old[key].iter() if e.get('id'))
    protected = [key for key in old if key not in permitted]
    missing = [key for key in protected if key not in new]
    changed = [key for key in protected if key in new
               and normalized(old[key]) != normalized(new[key])]
    order_ok = [key for key in protected if key in new] == [key for key in new if key in protected]
    spacing = []
    siblings = list(after)
    for i, e in enumerate(siblings):
        if not re.fullmatch(r'h[1-6]', e.tag) or i == 0:
            continue
        previous = siblings[i - 1]
        if previous.tag == 'title' or re.fullmatch(r'h[1-6]', previous.tag):
            continue
        if previous.tag != 'p' or text(previous):
            spacing.append({'id': e.get('id'), 'heading': text(e), 'issue': 'missing blank paragraph'})
        elif i > 1 and siblings[i - 2].tag == 'p' and not text(siblings[i - 2]):
            spacing.append({'id': e.get('id'), 'heading': text(e), 'issue': 'repeated blank paragraphs'})
    resources = resource_list(after)
    tokens = [r['token'] for r in resources if r['token']]
    duplicate_tokens = [k for k, n in Counter(tokens).items() if n > 1]
    image_sources = [r['src'] for r in resources if r['tag'] == 'img' and r['src']]
    duplicate_images = [k for k, n in Counter(image_sources).items() if n > 1]
    return {
        'protected_blocks': len(protected), 'unexpected_missing': missing,
        'unexpected_changed': changed, 'protected_order_preserved': order_ok,
        'heading_spacing_errors': spacing,
        'removed_allowed_ids': sorted(set(old) - set(new) - set(missing)),
        'new_ids': [key for key in new if key not in old],
        'resources_before': resource_list(before), 'resources_after': resources,
        'duplicate_resource_tokens_review': duplicate_tokens,
        'duplicate_image_sources_review': duplicate_images,
        'pass': not missing and not changed and order_ok and not spacing,
        'limits': 'Does not verify source truth, expected new content, resource pixels, or native board node changes.'
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', required=True)
    parser.add_argument('--after', required=True)
    parser.add_argument('--allow-changes', help='JSON array of explicitly allowed old block IDs')
    parser.add_argument('--output', help='New report file; refuses overwrite')
    args = parser.parse_args()
    before, rb = read_document(args.before)
    after, ra = read_document(args.after)
    allowed = json.loads(Path(args.allow_changes).read_text()) if args.allow_changes else []
    if not isinstance(allowed, list) or any(not isinstance(i, str) for i in allowed):
        raise ValueError('allow-changes must contain a JSON array of IDs')
    result = audit(before, after, allowed)
    result.update(revision_before=rb, revision_after=ra)
    output = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        with Path(args.output).open('x', encoding='utf-8') as handle:
            handle.write(output)
    print(output, end='')
    return 0 if result['pass'] else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, ET.ParseError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        sys.exit(2)
