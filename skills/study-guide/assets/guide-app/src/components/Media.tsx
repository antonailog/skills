import { useState } from 'react'
import { ExternalLink, Play } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Video } from '@/types'

// 视频卡（::video A | B，videos.json 按 name 对）：能嵌就嵌，不能嵌的显示封面卡、点了开原地址
// - mp4：<video>，双击打开的本地页面也能播
// - youtube：先放封面，点了再加载播放器（一页好几个播放器一起加载太慢）；双击打开（file://）时 YouTube 会报错，点了直接去 YouTube 看

const served = typeof location !== 'undefined' && location.protocol.startsWith('http')

export function ytId(s: string | null | undefined): string | null {
  if (!s) return null
  if (/^[\w-]{11}$/.test(s)) return s
  const m = s.match(/(?:youtube\.com\/(?:watch\?v=|shorts\/|embed\/)|youtu\.be\/)([\w-]{11})/)
  return m ? m[1] : null
}

const vertical = (v: Video) => /shorts\//.test(`${v.youtube ?? ''} ${v.url ?? ''}`)

export function Screen({ v }: { v: Video }) {
  const [on, setOn] = useState(false)
  const yt = ytId(v.youtube) ?? ytId(v.url)
  const img = v.poster ?? (yt ? `https://i.ytimg.com/vi/${yt}/hqdefault.jpg` : null)
  const box = cn('relative block w-full overflow-hidden rounded-md border bg-muted', vertical(v) ? 'aspect-[9/16]' : 'aspect-video')
  if (v.mp4) return <video className={cn(box, 'bg-black object-contain')} src={v.poster ? v.mp4 : `${v.mp4}#t=0.5`} poster={v.poster ?? undefined} controls playsInline preload={v.poster ? 'none' : 'metadata'} />
  const src = yt && served ? `https://www.youtube.com/embed/${yt}?autoplay=1&rel=0&playsinline=1` : null
  if (on && src) return <iframe className={box} src={src} title={v.name} allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowFullScreen referrerPolicy="strict-origin-when-cross-origin" />
  const face = (
    <>
      {img && <img src={img} alt="" loading="lazy" className="absolute inset-0 size-full object-cover" />}
      <span className="absolute inset-0 grid place-items-center">
        <span className="grid size-12 place-items-center rounded-full bg-black/60 text-white transition-transform duration-150 group-hover/v:scale-110">
          {src ? <Play className="ml-0.5 size-5 fill-current" /> : <ExternalLink className="size-5" />}
        </span>
      </span>
    </>
  )
  if (src) return <button type="button" className={cn(box, 'group/v cursor-pointer')} onClick={() => setOn(true)} aria-label={`播放：${v.name}`}>{face}</button>
  return <a className={cn(box, 'group/v')} href={v.url ?? (yt ? `https://www.youtube.com/watch?v=${yt}` : undefined)} target="_blank" rel="noopener" aria-label={`打开：${v.name}`}>{face}</a>
}

/** 视频下面一行：名字（有原地址就点了去原地址） */
function Meta({ v }: { v: Video }) {
  const href = v.url ?? (ytId(v.youtube) ? `https://www.youtube.com/watch?v=${ytId(v.youtube)}` : null)
  return href
    ? <a href={href} target="_blank" rel="noopener" className="flex items-start gap-1.5 font-medium hover:text-brand"><span className="min-w-0">{v.name}</span><ExternalLink className="mt-1 size-3.5 shrink-0" /></a>
    : <span className="font-medium">{v.name}</span>
}

/** 一组视频：横屏只有一条时整栏宽，两条以上一行两个（手机上一行一个）；竖屏一行三个 */
export function MediaGroup({ items }: { items: Video[] }) {
  const tall = items.filter(vertical)
  const wide = items.filter((v) => !vertical(v))
  return (
    <div className="fig-flat flex flex-col gap-6">
      {wide.length > 0 && (
        <div className={cn('grid gap-x-4 gap-y-6', wide.length > 1 && 'grid-cols-2 max-[640px]:grid-cols-1')}>
          {wide.map((v, i) => <figure key={`w${i}`} className="m-0 flex flex-col gap-2.5"><Screen v={v} /><Meta v={v} /></figure>)}
        </div>
      )}
      {tall.length > 0 && (
        <div className="grid grid-cols-3 gap-4 max-[460px]:grid-cols-2">
          {tall.map((v, i) => <figure key={`t${i}`} className="m-0 flex flex-col gap-2.5"><Screen v={v} /><Meta v={v} /></figure>)}
        </div>
      )}
    </div>
  )
}
