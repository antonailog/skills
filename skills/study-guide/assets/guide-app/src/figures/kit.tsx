import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

// 自定义演示共用的零件

/** 演示的外框：白卡细边，里面用界面字（14 号）；下方一行灰字说明 */
export function Figure({ children, caption, className }: { children: ReactNode; caption?: ReactNode; className?: string }) {
  return (
    <figure className="fig-box">
      <div className={cn('fig-panel', className)}>{children}</div>
      {caption && <figcaption className="fig-cap">{caption}</figcaption>}
    </figure>
  )
}

/** 演示里的选项按钮：和顶栏导航同一种胶囊，当前项黄绿浅底 */
export function Pill({ on, onClick, children }: { on?: boolean; onClick?: () => void; children: ReactNode }) {
  return <button type="button" className={cn('pill', on && 'on')} onClick={onClick} aria-pressed={on}>{children}</button>
}
