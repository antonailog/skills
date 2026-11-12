import { useMemo } from 'react'
import { BackMobile, Fab, Side, TocMobile, useScrollSpy, type TocItem } from '@/components/Side'
import { GuideBody, Hash } from '@/components/Guide'
import { SrcMeta } from '@/components/Cite'
import { Inline } from '@/components/Md'
import { guide } from '@/data'

// 版式照博客文章页（post.css 的 .pg）：左栏返回 + 目录 | 正文 820 | 右边留空，正文在页面正中。
// 内容全在学习指南目录的 guide.md；站名、导航、返回链接、页脚在 site.config.json
const BACK = guide.back ?? { href: '/', label: '返回' }

export default function App() {
  const ids = useMemo(() => [...guide.heads.map((h) => h.id), 'refs'], [])
  const [active, pick] = useScrollSpy(ids)
  const refsIn = guide.refs?.parent   // 来源列表挂在「其他」这一章下
  const curChapter = (() => {
    if (active === 'refs') return refsIn ?? 'refs'
    const i = guide.heads.findIndex((h) => h.id === active)
    for (let k = i; k >= 0; k--) if (guide.heads[k].level === 2) return guide.heads[k].id
    return null
  })()
  const hasRefs = guide.sources.length > 0
  // 目录：章全列（两位编号），当前这章展开到小节；章名、小节名取冒号前面那段
  const chapters = guide.heads.filter((h) => h.level === 2)
  const chapterItem = (c: (typeof chapters)[number]): TocItem => ({ id: c.id, n: c.n ?? undefined, label: (c.title ?? c.text).split('：')[0] })
  const refsSub: TocItem = { id: 'refs', label: '来源', sub: true }
  const refsOwn: TocItem[] = hasRefs && !refsIn ? [{ id: 'refs', n: guide.refs?.n, label: '来源' }] : []
  const items: TocItem[] = [
    ...chapters.flatMap((c) => {
      const subs: TocItem[] = guide.heads.filter((h) => h.level === 3 && h.id.startsWith(`${c.id}-`)).map((s) => ({ id: s.id, label: s.text.split('：')[0], sub: true }))
      if (hasRefs && refsIn === c.id) subs.push(refsSub)
      return [chapterItem(c), ...(curChapter === c.id ? subs : [])]
    }),
    ...refsOwn,
  ]
  const allItems: TocItem[] = [...chapters.map(chapterItem), ...refsOwn]
  return (
    <>
      <div className="pg">
        <Side items={items} active={active} pick={pick} back={BACK} />
        <main className="post">
          <BackMobile back={BACK} />
          <header className="post-head">
            <h1 className="text-balance break-keep">{guide.title}</h1>
            <p className="meta"><time dateTime={guide.date}>{guide.date}</time><span className="dot">·</span><span>约 {guide.minutes} 分钟</span></p>
            {guide.lede && <div className="lede"><Inline md={guide.lede} /></div>}
          </header>
          <TocMobile items={allItems} active={curChapter} />
          <article className="prose"><GuideBody /></article>
          {hasRefs && (
            <section id="refs" className={refsIn ? 'refs in' : 'refs'} aria-labelledby="refs-h">
              {refsIn
                ? <h3 id="refs-h">来源<Hash id="refs" /></h3>
                : <h2 id="refs-h">{guide.refs?.n && <span className="hn" aria-hidden="true">{guide.refs.n}</span>}来源<Hash id="refs" /></h2>}
              <p>正文里的编号对应这里。</p>
              <ol>
                {guide.sources.map((s) => (
                  <li key={s.id} id={`ref-${s.n}`}>
                    <span>[{s.n}]</span>
                    <span className="flex flex-col gap-0.5">
                      {s.url ? <a href={s.url} target="_blank" rel="noopener">{s.title ?? s.url}</a> : <span>{s.title ?? s.id}</span>}
                      <SrcMeta s={s} />
                    </span>
                  </li>
                ))}
              </ol>
            </section>
          )}
        </main>
        <div className="side-r" aria-hidden="true" />
      </div>
      <Fab />
    </>
  )
}
