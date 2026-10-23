#!/usr/bin/env python3
"""取一期 Podwise 单集并归档：转写、全部 AI 字段、个人摘录、CLI 缓存里的原始对象（含元数据与 Shownotes HTML）。
同时生成通读用的按说话人合并稿、Shownotes 文本、全部原始资料 md 与资料包 zip。

用法：python3 fetch_episode.py <单集 URL 或编号> <工作区单集目录> <结果区单集目录>
已存在的源文件不重复下载；加 --refresh 才重取。"""
import argparse, datetime, hashlib, html, json, pathlib, re, shutil, subprocess, sys, zipfile

def sh(args, out):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"失败：{' '.join(args[:3])}… {r.stderr.strip()[:300]}")
    out.write_text(r.stdout, encoding='utf-8')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('episode'); ap.add_argument('workdir'); ap.add_argument('resultdir'); ap.add_argument('--refresh', action='store_true')
    a = ap.parse_args()
    eid = re.search(r'(\d+)\s*$', a.episode.rstrip('/')).group(1)
    url = f'https://app.podwise.ai/dashboard/episodes/{eid}'
    W = pathlib.Path(a.workdir); R = pathlib.Path(a.resultdir); S = W / 'sources'
    for d in (S, W / 'figs', W / 'evidence', R / 'images'): d.mkdir(parents=True, exist_ok=True)
    jobs = [(['podwise', 'get', 'transcript', url, '--format', 'json'], 'raw-transcript.json')]
    jobs += [(['podwise', 'get', k, url], f'podwise-{k}.md') for k in ('summary', 'chapters', 'qa', 'highlights', 'keywords', 'mindmap')]
    jobs += [(['podwise', 'clip', 'list', url, '--json'], 'clips.json')]
    for args, name in jobs:
        if a.refresh or not (S / name).exists(): sh(args, S / name)
    cache = pathlib.Path.home() / '.cache' / 'podwise'
    for src, dst in ((f'{eid}_summary.json', 'raw-summary.json'), (f'{eid}_transcript.json', 'raw-transcript-full.json')):
        if not (cache / src).exists(): sys.exit(f'CLI 缓存里没有 {src}；先确认 podwise 已登录且上面的命令成功')
        shutil.copyfile(cache / src, S / dst)
    ep = json.loads((S / 'raw-summary.json').read_text(encoding='utf-8'))['episode']
    segs = json.loads((S / 'raw-transcript-full.json').read_text(encoding='utf-8'))['segments']
    desc = ep.get('description', '')
    (S / 'show-notes-original.html').write_text(desc, encoding='utf-8')
    txt = re.sub(r'<br\s*/?>', '\n', desc); txt = re.sub(r'</p>|</li>|</h\d>', '\n', txt); txt = re.sub(r'<li>', '- ', txt)
    txt = html.unescape(re.sub(r'<[^>]+>', '', txt)); txt = re.sub(r'\n{3,}', '\n\n', txt).strip()
    (S / 'show-notes.md').write_text(txt, encoding='utf-8')
    imgs = re.findall(r'<img[^>]+src="([^"]+)"', desc)
    # 通读稿：连续同一说话人合并成段
    paras, cur = [], None
    for x in segs:
        sp, tm, c = x.get('speaker', ''), x.get('time') or x.get('start'), x.get('content', '').strip()
        if cur and cur[1] == sp: cur[2].append(c)
        else:
            if cur: paras.append(cur)
            cur = [tm, sp, [c]]
    if cur: paras.append(cur)
    (S / 'transcript-paras.txt').write_text('\n\n'.join(f"[{t}] {s}：{''.join(c)}" for t, s, c in paras), encoding='utf-8')
    tz = datetime.timezone(datetime.timedelta(hours=8)); pub = datetime.datetime.fromtimestamp(ep['publishTime'], tz)
    dur = ep['duration']; hms = f'{dur // 3600:02d}:{dur % 3600 // 60:02d}:{dur % 60:02d}'
    parts = [f"# {ep['title']}｜全部原始资料\n",
             '> 来源：Podwise CLI 单集数据与本机响应缓存。正文保留来源措辞，只调整排版；未做总结、改写或纠错。转写为机器转写，专名以 Shownotes 为准。\n',
             '## 1. 播客信息\n',
             f"- 播客：{ep['podcastName']}\n- 单集：{ep['title']}\n- 单集编号：{ep['seq']}\n- 发布时间：{pub:%Y-%m-%d %H:%M}（Asia/Shanghai）\n- 时长：{hms}\n- 转写段数：{len(segs)}\n- [Podwise 单集页面]({url})\n- [原音频]({ep['link']})\n- [单集封面]({ep.get('epCover') or ep.get('cover')})\n",
             '## 2. 节目原始简介 / Show Notes\n', txt + '\n', '## 3. 完整转写原文\n']
    parts += [f"**[{x.get('time') or x.get('start')}] {x.get('speaker', '')}**\n\n{x.get('content', '')}\n" for x in segs]
    for k, n in (('summary', '4. Podwise 总结与关键要点'), ('chapters', '5. Podwise 章节'), ('qa', '6. Podwise 问答'), ('highlights', '7. Podwise 高亮'), ('keywords', '8. Podwise 关键词'), ('mindmap', '9. Podwise 思维导图')):
        parts.append(f'## {n}（原文）\n\n' + (S / f'podwise-{k}.md').read_text(encoding='utf-8') + '\n')
    parts.append('## 10. 个人摘录（clips）\n\n```json\n' + (S / 'clips.json').read_text(encoding='utf-8') + '\n```\n')
    (R / f'{eid}-全部原始资料.md').write_text('\n'.join(parts), encoding='utf-8')
    files = sorted(p for p in S.iterdir() if p.is_file())
    man = {'episode': eid, 'created': datetime.datetime.now(tz).isoformat(timespec='seconds'), 'files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (W / 'source-manifest.json').write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding='utf-8')
    with zipfile.ZipFile(R / f'{eid}-原始资料包.zip', 'w', zipfile.ZIP_DEFLATED) as z:
        for p in files: z.write(p, f'sources/{p.name}')
        z.write(W / 'source-manifest.json', 'source-manifest.json')
    print(json.dumps({'episode': eid, 'title': ep['title'], 'podcast': ep['podcastName'], 'publish': f'{pub:%Y-%m-%d}', 'duration': hms,
                      'segments': len(segs), 'speakers': sorted({x.get('speaker', '') for x in segs}), 'chars': sum(len(x.get('content', '')) for x in segs),
                      'shownotes_images': imgs, 'cover': ep.get('epCover') or ep.get('cover'), 'read_file': str(S / 'transcript-paras.txt')}, ensure_ascii=False, indent=1))

if __name__ == '__main__':
    main()
