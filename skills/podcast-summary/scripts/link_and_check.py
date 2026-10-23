#!/usr/bin/env python3
"""飞书页收尾：把问答答案末尾的「→ A1」换成指向该单元标题块的锚点链接，再回读核对。
核对项：一级标题顺序、各级标题前空段、问答锚点全部指向存在的单元标题、强调标记计数、画板／图片／附件／表格数量。

用法：python3 link_and_check.py <docx token> <wiki 节点 URL> [--check-only]
锚点用 wiki 节点 URL，不用 docx URL。已链接过的页只跑 --check-only，避免重复替换。"""
import argparse, json, re, subprocess, os
ENV = {**os.environ, 'LARKSUITE_CLI_NO_UPDATE_NOTIFIER': '1', 'LARKSUITE_CLI_NO_SKILLS_NOTIFIER': '1'}

def fetch(doc):
    r = subprocess.run(['lark-cli', 'docs', '+fetch', '--doc', doc, '--api-version', 'v2', '--detail', 'with-ids', '--as', 'user', '--json'], capture_output=True, text=True, env=ENV)
    o = r.stdout; return json.loads(o[o.find('{'):])['data']['document']

def unit_ids(c):
    ids = {}
    for lvl, bid, txt in re.findall(r'<h([1-4]) id="([^"]+)">(.*?)</h\1>', c):
        m = re.match(r'([A-Z]\d+) ', re.sub(r'<[^>]+>', '', txt))
        if m: ids[m.group(1)] = bid
    return ids

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('doc'); ap.add_argument('wiki_url'); ap.add_argument('--check-only', action='store_true')
    a = ap.parse_args(); doc = fetch(a.doc); c = doc['content']; ids = unit_ids(c); res = {}
    if not a.check_only:
        codes = sorted(set(re.findall(r'→ ([A-Z]\d+)(?!</a>)', c))); done, fail = 0, []
        for code in codes:
            if code not in ids: fail.append(code); continue
            r = subprocess.run(['lark-cli', 'docs', '+update', '--doc', a.doc, '--command', 'str_replace', '--pattern', f'→ {code}',
                                '--content', f'→ <a href="{a.wiki_url}#{ids[code]}">{code}</a>', '--as', 'user', '--json'], capture_output=True, text=True, env=ENV)
            o = r.stdout
            try: ok = json.loads(o[o.find('{'):]).get('ok')
            except Exception: ok = False
            done += 1 if ok else 0
            if not ok: fail.append(code)
        res['anchored'] = done; res['anchor_fail'] = fail
        doc = fetch(a.doc); c = doc['content']; ids = unit_ids(c)
    links = re.findall(re.escape(a.wiki_url) + r'#([^"]+)">([A-Z]\d+)</a>', c); heads = set(ids.values())
    blocks = re.findall(r'<(h[1-4]|p|ul|ol|table|img|whiteboard|figure|title)\b[^>]*>(.*?)</\1>|<(img|whiteboard)\b[^>]*/>', c, flags=re.S)
    seq = [((x or z), (y or '').strip()) for x, y, z in blocks]; bad = []
    for i, (tg, inner) in enumerate(seq):
        if tg[0] == 'h' and tg != 'h' and i > 0:
            ptg, pin = seq[i - 1]
            if not (ptg[0] == 'h' or ptg == 'title' or (ptg == 'p' and pin == '')): bad.append(re.sub(r'<[^>]+>', '', inner)[:24])
    res.update({'revision': doc.get('revision_id'), 'h1_order': [re.sub(r'<[^>]+>', '', x) for x in re.findall(r'<h1 id="[^"]+">(.*?)</h1>', c)],
                'units': len(ids), 'qa_links': len(links), 'qa_links_valid': all(b in heads for b, _ in links), 'headings_without_spacer': bad,
                'counts': {k: c.count(v) for k, v in (('whiteboard', '<whiteboard'), ('img', '<img '), ('attachment', '<source'), ('table', '<table'), ('bold', '<b>'), ('underline', '<u>'), ('highlight', '<span'), ('italic', '<em>'))}})
    print(json.dumps(res, ensure_ascii=False, indent=1))

if __name__ == '__main__':
    main()
