import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card'
import { Globe } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { Source } from '@/types'

// 引用编号 [n]：等宽小字；悬停看来源（来源名、网站图标 + 网站、日期），点了开原网页；没有 url 的来源只显示名字

/** 网站图标 + 网站 · 日期（引用浮窗和文末来源列表共用）；没下载到图标的用通用地球图标 */
const hostOf = (u?: string | null) => { try { return u ? new URL(u).hostname.replace(/^www\./, '') : null } catch { return null } }

export function SrcMeta({ s }: { s: Source }) {
  const site = s.site ?? hostOf(s.url)   // 来源表里没写网站名时用域名
  if (!site && !s.date) return null
  return (
    <span className="src-meta">
      {s.icon ? <img src={s.icon} alt="" loading="lazy" /> : s.url ? <Globe aria-hidden="true" /> : null}
      <span>{[site, s.date].filter(Boolean).join(' · ')}</span>
    </span>
  )
}

export function Cite({ s }: { s: Source }) {
  return (
    <HoverCard openDelay={120} closeDelay={100}>
      <HoverCardTrigger asChild>
        <a data-cite className={cn('cite', !s.url && 'none')} href={s.url ?? undefined} target={s.url ? '_blank' : undefined} rel="noopener">[{s.n}]</a>
      </HoverCardTrigger>
      <HoverCardContent align="start" className="kb-pop flex w-max min-w-[12rem] max-w-[min(24rem,calc(100vw-32px))] flex-col gap-2 p-4">
        {s.url
          ? <a href={s.url} target="_blank" rel="noopener" className="font-medium hover:text-brand">{s.title ?? s.url} ↗</a>
          : <span className="font-medium">{s.title ?? s.id}</span>}
        <SrcMeta s={s} />
      </HoverCardContent>
    </HoverCard>
  )
}
