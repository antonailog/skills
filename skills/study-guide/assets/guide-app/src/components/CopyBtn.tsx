import { useEffect, useRef, useState } from 'react'
import { Check, Copy } from 'lucide-react'
import { cn } from '@/lib/utils'

/** 复制按钮（代码块、提示词块共用）：平时「复制图标 + 复制」；点了换成「对号 + 已复制」、浅强调色底，停 1.6 秒再回来；复制失败显示「复制失败」 */
export function CopyBtn({ text, className }: { text: string; className: string }) {
  const [state, setState] = useState<'idle' | 'done' | 'fail'>('idle')
  const timer = useRef(0)
  useEffect(() => () => clearTimeout(timer.current), [])
  const show = (s: 'done' | 'fail') => { setState(s); clearTimeout(timer.current); timer.current = window.setTimeout(() => setState('idle'), 1600) }
  const copy = () => (navigator.clipboard ? navigator.clipboard.writeText(text).then(() => show('done'), () => show('fail')) : show('fail'))
  return (
    <button type="button" className={cn(className, state === 'done' && 'done', state === 'fail' && 'fail')} onClick={copy} aria-live="polite">
      {state === 'done' ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
      <span>{state === 'done' ? '已复制' : state === 'fail' ? '复制失败' : '复制'}</span>
    </button>
  )
}
