#!/usr/bin/env python3
"""把本地 SVG 写进飞书画板：whiteboard-cli 转 openapi → 每个节点显式 z_index → 文本框按飞书字宽放宽（居中／右对齐补偿 x）
→ 唯一幂等 token 覆盖写入 → 等待后导出云端预览与 raw 节点数。实测约束见 references/visuals.md。

用法（在 SVG 所在目录或其上层执行；lark-cli 只收相对当前目录的路径）：
  python3 write_boards.py --outdir boards 骨架图.svg:<board_token> 总结图.svg:<board_token> ...
  --dry-run 只转换和放宽，不写入。"""
import argparse, json, pathlib, subprocess, time, unicodedata, os

ENV = {**os.environ, 'LARKSUITE_CLI_NO_UPDATE_NOTIFIER': '1', 'LARKSUITE_CLI_NO_SKILLS_NOTIFIER': '1'}
def est(t, fs): return sum(1.0 if unicodedata.east_asian_width(c) in ('W', 'F') else 0.65 for c in t) * fs * 1.08 + 10
def run(args):
    r = subprocess.run(args, capture_output=True, text=True, env=ENV); t = r.stdout
    try: return json.loads(t[t.find('{'):])
    except Exception: return {'ok': False, 'raw': (t + r.stderr)[:300]}

def prepare(svg, outdir):
    js = subprocess.run(['npx', '-y', '@larksuite/whiteboard-cli@^0.2.13', '-i', str(svg), '-f', 'svg', '--to', 'openapi', '--format', 'json'], capture_output=True, text=True, env=ENV).stdout
    nodes = json.loads(js)['data']['result']['nodes']; widened = 0
    for i, n in enumerate(nodes):
        n['z_index'] = i; t = n.get('text', {}).get('text', '')
        if n['type'] == 'text_shape' and t:
            ow = n.get('width', 0); nw = max(ow, est(t, n['text'].get('font_size', 20)))
            if nw > ow:
                al = n['text'].get('horizontal_align', 'left')
                if al == 'center': n['x'] = n.get('x', 0) - (nw - ow) / 2
                elif al == 'right': n['x'] = n.get('x', 0) - (nw - ow)
                n['width'] = nw; widened += 1
    out = outdir / f'{svg.stem}.z.json'; out.write_text(json.dumps({'nodes': nodes}, ensure_ascii=False), encoding='utf-8')
    return out, len(nodes), widened, sum(1 for n in nodes if n['type'] == 'connector')

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('pairs', nargs='+'); ap.add_argument('--outdir', default='boards'); ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(); outdir = pathlib.Path(a.outdir); outdir.mkdir(parents=True, exist_ok=True); report = []
    for k, pair in enumerate(a.pairs):
        svg, tok = pair.rsplit(':', 1); svg = pathlib.Path(svg)
        z, n, w, c = prepare(svg, outdir); item = {'svg': str(svg), 'token': tok, 'nodes': n, 'widened': w, 'connectors': c}
        if not a.dry_run:
            r = run(['lark-cli', 'whiteboard', '+update', '--whiteboard-token', tok, '--input_format', 'raw', '--source', '@' + os.path.relpath(z),
                     '--overwrite', '--idempotent-token', f'{tok[:8]}-{k}-{int(time.time() * 1000)}', '--as', 'user', '--json'])
            item['written'] = bool(r.get('ok'))
            if not r.get('ok'): item['error'] = r
        report.append(item)
    if not a.dry_run:
        time.sleep(15)
        for item in report:
            prev = outdir / f"{pathlib.Path(item['svg']).stem}.preview.jpg"
            r = run(['lark-cli', 'whiteboard', '+export', '--whiteboard-token', item['token'], '--output-type', 'preview', '--output', str(prev), '--overwrite', '--as', 'user', '--json'])
            item['preview'] = str(prev) if r.get('ok') else r
            raw = run(['lark-cli', 'whiteboard', '+export', '--whiteboard-token', item['token'], '--output-type', 'raw', '--as', 'user', '--json'])
            item['cloud_nodes'] = len(raw.get('data', {}).get('nodes', []))
    print(json.dumps(report, ensure_ascii=False, indent=1))

if __name__ == '__main__':
    main()
