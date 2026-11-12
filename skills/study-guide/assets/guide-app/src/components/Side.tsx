import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { cn } from '@/lib/utils'

// 左栏：和文章页同一套（post.css 的 .side / .toc / .btn / .totop / .toc-m / .fab），这里只负责数据和滚动联动
// 目录：章带两位编号（等宽深黄绿），没编号的章留空位对齐；当前章展开到小节（指南有 30 多个小节，全列太长）

export type TocItem = { id: string; label: string; n?: string; sub?: boolean }

const Back = () => <svg className="ln" viewBox="0 0 24 24" aria-hidden="true"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
const Up = () => <svg className="ln" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7" /></svg>
const Ring = ({ p }: { p: number }) => (
  <svg className="ring" viewBox="0 0 40 40" aria-hidden="true">
    <circle className="tk" cx="20" cy="20" r="17" />
    <circle className="pr" cx="20" cy="20" r="17" style={{ strokeDashoffset: 106.8 * (1 - p) }} />
  </svg>
)

/** 阅读进度和「回到顶部」是否露出 */
export function useScrollState() {
  const [s, set] = useState({ p: 0, show: false })
  useEffect(() => {
    const on = () => {
      const max = document.documentElement.scrollHeight - innerHeight
      set({ p: max > 0 ? Math.min(1, scrollY / max) : 0, show: scrollY > innerHeight * 0.8 })
    }
    on()
    addEventListener('scroll', on, { passive: true })
    addEventListener('resize', on)
    return () => { removeEventListener('scroll', on); removeEventListener('resize', on) }
  }, [])
  return s
}

/** 当前小节：最后一个滚过顶栏下沿的标题；点了目录就锁定，直到用户自己滚 */
export function useScrollSpy(ids: string[]) {
  const [active, setActive] = useState<string | null>(null)
  const lock = useRef<string | null>(null)
  useEffect(() => {
    const cur = () => {
      if (lock.current) return lock.current
      let c: string | null = null
      const end = innerHeight + scrollY >= document.documentElement.scrollHeight - 4
      for (const id of ids) {
        const t = document.getElementById(id)?.getBoundingClientRect().top
        if (t !== undefined && (t <= 120 || (end && t < innerHeight - 80))) c = id
      }
      return c
    }
    const tick = () => setActive(cur())
    const unlock = () => { lock.current = null }
    tick()
    addEventListener('scroll', tick, { passive: true })
    const evs = ['wheel', 'touchmove', 'keydown', 'pointerdown'] as const
    evs.forEach((e) => addEventListener(e, unlock, { passive: true }))
    return () => { removeEventListener('scroll', tick); evs.forEach((e) => removeEventListener(e, unlock)) }
  }, [ids])
  return [active, (id: string) => { lock.current = id; setActive(id) }] as const
}

type Box = { y: number; h: number }
const toTop = () => scrollTo({ top: 0, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })

export function Side({ items, active, pick, back }: { items: TocItem[]; active: string | null; pick: (id: string) => void; back: { href: string; label: string } }) {
  const { p, show } = useScrollState()
  const list = useRef<HTMLOListElement>(null)
  const nav = useRef<HTMLElement>(null)
  const links = useRef<Record<string, HTMLAnchorElement | null>>({})
  const [ind, setInd] = useState<Box | null>(null)
  const [hover, setHover] = useState<string | null>(null)
  const [ghost, setGhost] = useState<Box | null>(null)
  const at = (id: string | null): Box | null => {
    const a = id ? links.current[id] : null, o = list.current
    return a && o ? { y: a.getBoundingClientRect().top - o.getBoundingClientRect().top, h: a.offsetHeight } : null
  }
  useLayoutEffect(() => {
    setInd(at(active))
    const a = active ? links.current[active] : null, box = nav.current   // 目录比栏高时，把当前项滚进目录可见范围（只滚目录）
    if (a && box) {
      const ar = a.getBoundingClientRect(), br = box.getBoundingClientRect()
      if (ar.top < br.top + 24 || ar.bottom > br.bottom - 24) box.scrollTo({ top: box.scrollTop + ar.top - br.top - br.height / 3 })
    }
  }, [active, items]) // eslint-disable-line react-hooks/exhaustive-deps
  useLayoutEffect(() => { if (hover) setGhost(at(hover)) }, [hover]) // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <aside className="side" aria-label="返回和目录">
      <div className="side-in">
        <a className="btn back" href={back.href}><Back /><span>{back.label}</span></a>
        <nav ref={nav} className="toc" aria-label="本页目录">
          <p className="toc-h">目录</p>
          <ol ref={list} onMouseLeave={() => setHover(null)}>
            <i aria-hidden className={cn('toc-ghost', hover && ghost && 'show')} style={ghost ? { transform: `translateY(${ghost.y}px)`, height: ghost.h } : undefined} />
            <i aria-hidden className={cn('toc-ind', ind && 'show')} style={ind ? { transform: `translateY(${ind.y}px)`, height: ind.h } : undefined} />
            {items.map((t) => (
              <li key={t.id} className={t.sub ? 'u' : 's'}>
                <a ref={(el) => { links.current[t.id] = el }} href={`#${t.id}`} className={cn(active === t.id && 'on')} aria-current={active === t.id ? 'true' : undefined}
                  onMouseEnter={() => setHover(t.id)} onClick={() => pick(t.id)}>
                  {!t.sub && <span className="tn">{t.n ?? ''}</span>}
                  <span>{t.label}</span>
                </a>
              </li>
            ))}
          </ol>
        </nav>
        <button className={cn('btn totop', show && 'show')} type="button" onClick={toTop}><span className="ic"><Ring p={p} /><Up /></span><span>回到顶部</span></button>
      </div>
    </aside>
  )
}

/** 窄屏（< 1100px）：返回按钮在标题上方、目录折叠在导语下、右下角回到顶部（post.css 负责什么时候显示） */
export function BackMobile({ back }: { back: { href: string; label: string } }) {
  return <a className="btn back back-m" href={back.href}><Back /><span>{back.label}</span></a>
}

export function TocMobile({ items, active }: { items: TocItem[]; active: string | null }) {
  return (
    <details className="toc-m">
      <summary>目录</summary>
      <ol>
        {items.map((t) => (
          <li key={t.id} className={t.sub ? 'u' : 's'}>
            <a href={`#${t.id}`} className={cn(active === t.id && 'on')}>{!t.sub && <span className="tn">{t.n ?? ''}</span>}<span>{t.label}</span></a>
          </li>
        ))}
      </ol>
    </details>
  )
}

export function Fab() {
  const { p, show } = useScrollState()
  return <button className={cn('fab', show && 'show')} type="button" onClick={toTop} aria-label="回到顶部" title="回到顶部"><span className="ic"><Ring p={p} /><Up /></span></button>
}
