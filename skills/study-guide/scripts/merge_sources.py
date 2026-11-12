"""把子 agent 找回的 links/<材料名>.json 并进 sources.json，正文就能用 [[材料名-n]] 引用（n 同 _todo 里的 n）。

links/<材料名>.json 每条：{id, url, title, site, date, status, note}。status、note 是给你和维护的人看的核对记录，不进 sources.json（页面不显示核对状态）。
已经手写在 sources.json 里的条目（id 不是「材料名-n」形式的）原样保留。
找回的链接失效、要换：
- 还是同一份来源，只是地址变了（搬了家、找到正式版或存档）：改 links/<材料名>.json 里那条的 url（标题、日期一起改），重跑本脚本；
  id 不变，guide.md 不用动。「材料名-n」的条目每次都从 links 重新生成，直接改 sources.json 会被覆盖。
- 换成另一份来源：在 sources.json 手写一条新 id，把 guide.md 里对应的 [[材料名-n]] 改成新 id；旧条目没人引，就不会出现在页面上。
用法：python3 -I merge_sources.py <学习指南目录>
"""
import json
import re
import sys
from pathlib import Path


def tidy(entry: str | None) -> str | None:
    """来源条目 → 来源名：表格行只取第一格；去掉访问日期、「可能过时」这类给核对者看的字（页面不放核对说明）"""
    if not entry:
        return None
    t = entry.strip()
    if t.startswith('|'):
        t = t.strip('|').split('|')[0]
    t = re.sub(r'^\d+\.\s*', '', t)
    t = re.sub(r'[（(][^（）()]*(访问|可能过时|未找到|核对)[^（）()]*[）)]', '', t)
    t = re.sub(r'\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}日?\s*访问|访问日期[:：]?\s*\S*|，?可能过时', '', t)
    t = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', t).split('。')[0]
    return re.sub(r'\s+', ' ', t).strip(' ，,;；:：') [:80] or None


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    d = Path(sys.argv[1]).expanduser().resolve()
    f = d / 'sources.json'
    keep = [s for s in (json.loads(f.read_text(encoding='utf-8')) if f.exists() else []) if not s.get('_from_links')]
    merged, missing = [], 0
    for todo in sorted((d / 'links').glob('_todo-*.json')):
        stem = todo.stem[len('_todo-'):]
        found = {x['id']: x for x in json.loads((d / 'links' / f'{stem}.json').read_text(encoding='utf-8'))} if (d / 'links' / f'{stem}.json').exists() else {}
        for t in json.loads(todo.read_text(encoding='utf-8')):
            x = found.get(t['id'], {})
            title = x.get('title') or tidy(t.get('entry')) or f'材料 {stem} 引用的来源'
            if not x.get('url'):
                missing += 1
            merged.append({'id': f'{stem}-{t["n"]}', 'title': title, 'url': x.get('url'), 'site': x.get('site'), 'date': x.get('date'), '_from_links': True,
                           **({'_status': x['status']} if x.get('status') else {})})
    f.write_text(json.dumps(keep + merged, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'sources.json：手写 {len(keep)} 条 + 材料引用 {len(merged)} 条（没找回链接的 {missing} 条：照样能引，卡片上只显示来源名）')
    weak = [m['id'] for m in merged if m.get('_status') and m['_status'] != '核对过']
    if weak:
        print(f'核对状态不是「核对过」的 {len(weak)} 条（正文引用它们时构建会提醒；要引就先自己核一遍原网页）：' + '、'.join(weak[:40]) + ('…' if len(weak) > 40 else ''))


if __name__ == '__main__':
    main()
