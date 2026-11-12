import { useState } from 'react'
import { Figure, Pill } from './kit'

// 示例演示（example/guide.md 的 ::fig pace）：拖配速，看 3、5、10 公里各要跑多久。换主题时可以删掉，并从 index.tsx 去掉登记

const DIST = [3, 5, 10]
const fmt = (s: number) => {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), r = Math.round(s % 60)
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}` : `${m}:${String(r).padStart(2, '0')}`
}
const PRESET = [{ label: '刚开始', s: 480 }, { label: '跑了两个月', s: 420 }, { label: '有基础', s: 360 }]

export function PaceDemo() {
  const [pace, setPace] = useState(480)   // 每公里秒数
  const max = DIST.at(-1)! * 540
  return (
    <Figure caption="配速每慢 30 秒，5 公里多花 2 分半。入门阶段先求跑完，不求配速。">
      <div className="flex flex-col gap-5">
        <div className="flex flex-wrap items-center gap-2">
          {PRESET.map((p) => <Pill key={p.s} on={pace === p.s} onClick={() => setPace(p.s)}>{p.label}</Pill>)}
        </div>
        <label className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <span className="text-muted-foreground">配速</span>
          <input type="range" min={300} max={540} step={15} value={pace} onChange={(e) => setPace(Number(e.target.value))}
            className="min-w-0 flex-1 accent-[var(--accent-ink)]" aria-label="配速（每公里）" />
          <span className="w-24 text-right font-mono tabular-nums">{fmt(pace)} / 公里</span>
        </label>
        <div className="flex flex-col gap-3">
          {DIST.map((d) => (
            <div key={d} className="grid grid-cols-[4.5em_minmax(0,1fr)_5em] items-center gap-3">
              <span className="text-muted-foreground">{d} 公里</span>
              <span className="h-2.5 overflow-hidden rounded-full bg-muted">
                <span className="block h-full rounded-full bg-chart-mark transition-[width] duration-200" style={{ width: `${(d * pace / max) * 100}%` }} />
              </span>
              <span className="text-right font-mono tabular-nums">{fmt(d * pace)}</span>
            </div>
          ))}
        </div>
      </div>
    </Figure>
  )
}
