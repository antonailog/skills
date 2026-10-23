#!/usr/bin/env python3
"""Create/verify an explicit source archive manifest. No network or credentials."""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def inside(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"path escapes source root: {name}")
    return path


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return {'bytes': path.stat().st_size, 'sha256': h.hexdigest()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['create', 'verify'])
    p.add_argument('--root', required=True)
    p.add_argument('--manifest', required=True, help='Relative path within root')
    p.add_argument('paths', nargs='*', help='Explicit source paths for create')
    a = p.parse_args()
    root = Path(a.root).resolve(strict=True)
    manifest = inside(root, a.manifest)
    if a.action == 'create':
        if not a.paths:
            p.error('create requires explicit source paths')
        files = {}
        for name in a.paths:
            src = inside(root, name)
            if not src.exists():
                raise ValueError(f'missing source path: {name}')
            candidates = sorted(src.rglob('*')) if src.is_dir() else [src]
            for path in candidates:
                resolved = inside(root, path.relative_to(root))
                if resolved.is_file() and resolved != manifest:
                    files[str(path.relative_to(root))] = digest(resolved)
        if not files:
            raise ValueError('source selection contains no files')
        manifest.parent.mkdir(parents=True, exist_ok=True)
        with manifest.open('x', encoding='utf-8') as out:
            json.dump({'version': 1, 'files': files}, out, ensure_ascii=False, indent=2)
            out.write('\n')
        result = {'created': str(manifest), 'files': len(files)}
    else:
        data = json.loads(manifest.read_text(encoding='utf-8'))
        if not isinstance(data.get('files'), dict) or not data['files']:
            raise ValueError('manifest must contain a nonempty files object')
        missing, changed = [], []
        for name, expected in data['files'].items():
            path = inside(root, name)
            if not path.is_file():
                missing.append(name)
            elif digest(path)['sha256'] != expected['sha256']:
                changed.append(name)
        result = {'files': len(data['files']), 'missing': missing,
                  'changed': changed, 'pass': not missing and not changed}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get('pass', True) else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        sys.exit(2)
