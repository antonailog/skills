import { useEffect, useRef, useState } from 'react'
import { ExternalLink } from 'lucide-react'
import { cn } from '@/lib/utils'
import { guide } from '@/data'

// 同 collect_refs.py 的 img_path：本身是图片扩展名就用它，否则补 .jpg（key 常带点，比如 figma.com）
const shotOf = (img: string) => img.includes('/') ? img : `img/sites/${/\.(jpe?g|png|webp)$/i.test(img) ? img : `${img}.jpg`}`

/** 截图画廊（```gallery，网站登记在 sites.json）：一排首屏截图，整张可点、新窗口打开网站；没有截图的站排成一行链接
 *  一排放不下时横向滚动：鼠标停在画廊上往下滚，画廊往右走（目标值 + 每帧插值，平滑不跳）；滚到头了再把滚轮交还给页面。
 *  触控板横滑、手机左右划照常；吸附只给手指（CSS 里 pointer: coarse）；两端还有内容时画一道渐隐 */
export function Gallery({ keys }: { keys: string[] }) {
  const ref = useRef<HTMLDivElement>(null)
  const [edge, setEdge] = useState({ l: false, r: false })
  const list = keys.map((k) => guide.sites[k]).filter(Boolean)
  const shots = list.filter((s) => s.img)
  const bare = list.filter((s) => !s.img)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const upd = () => {
      const l = el.scrollLeft > 2, r = el.scrollLeft < el.scrollWidth - el.clientWidth - 2
      setEdge((p) => (p.l === l && p.r === r ? p : { l, r }))
    }
    const still = matchMedia('(prefers-reduced-motion: reduce)').matches
    let target = 0, cur = 0, raf = 0
    const step = () => {
      cur += (target - cur) * 0.2
      if (Math.abs(target - cur) < 0.5) cur = target
      el.scrollLeft = cur
      raf = cur === target ? 0 : requestAnimationFrame(step)
    }
    const onWheel = (e: WheelEvent) => {
      if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) return
      const max = el.scrollWidth - el.clientWidth
      if (!raf) target = cur = el.scrollLeft
      if (max <= 0 || (e.deltaY > 0 && target >= max - 1) || (e.deltaY < 0 && target <= 1)) return
      e.preventDefault()
      const dy = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaMode === 2 ? e.deltaY * el.clientWidth : e.deltaY
      target = Math.max(0, Math.min(max, target + dy))
      if (still) { cur = target; el.scrollLeft = target; return }
      if (!raf) raf = requestAnimationFrame(step)
    }
    upd()
    el.addEventListener('scroll', upd, { passive: true })
    el.addEventListener('wheel', onWheel, { passive: false })
    window.addEventListener('resize', upd)
    return () => { cancelAnimationFrame(raf); el.removeEventListener('scroll', upd); el.removeEventListener('wheel', onWheel); window.removeEventListener('resize', upd) }
  }, [])
  const links = bare.length > 0 && (
    <p className="gal-bare">
      {bare.map((s) => <a key={s.key} href={s.url} target="_blank" rel="noopener" title={s.desc}>{s.name}</a>)}
    </p>
  )
  if (!shots.length) return links || null
  return (
    <>
      <div className={cn('gal', edge.l && 'gal-l', edge.r && 'gal-r')}>
        <div ref={ref} className="gal-track">
          {shots.map((s) => (
            <a key={s.key} href={s.url} target="_blank" rel="noopener" className="gal-i">
              <img src={shotOf(s.img!)} alt={`${s.name} 首屏`} loading="lazy" />
              <span>{s.name}<ExternalLink className="size-3.5 shrink-0" /></span>
              {s.meta && <em className="gal-meta">{s.meta}</em>}
              {s.desc && <small className="gal-desc">{s.desc}</small>}
            </a>
          ))}
        </div>
      </div>
      {links}
    </>
  )
}
