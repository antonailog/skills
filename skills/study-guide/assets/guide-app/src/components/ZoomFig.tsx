import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'

/** 单独成段的图：白框，点了全屏放大，点任意处、按 Esc 或右上角 × 关掉；加载失败整块不出（不留空框） */
export function ZoomFig({ src, alt }: { src: string; alt: string }) {
  const [open, setOpen] = useState(false)
  const [bad, setBad] = useState(false)
  useEffect(() => {
    if (!open) return
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    addEventListener('keydown', key)
    return () => { removeEventListener('keydown', key); document.body.style.overflow = prev }
  }, [open])
  if (bad) return null
  return (
    <>
      <figure className="tc-fig">
        <button type="button" className="tc-zoom" onClick={() => setOpen(true)} aria-label={`放大查看：${alt}`}>
          <img src={src} alt={alt} loading="lazy" onError={() => setBad(true)} />
        </button>
      </figure>
      {open && createPortal(
        <div className="lb" role="dialog" aria-modal="true" aria-label={alt} onClick={() => setOpen(false)}>
          <img src={src} alt={alt} />
          <button type="button" className="lb-x" aria-label="关闭">×</button>
        </div>,
        document.body,
      )}
    </>
  )
}
