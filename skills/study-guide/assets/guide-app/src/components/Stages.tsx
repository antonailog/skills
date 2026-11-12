import type { ReactNode } from 'react'
import { Bot, User } from 'lucide-react'
import type { Block } from '@/types'

// 中轴两栏（```stages，人和 AI 分工）：
// - 中间一根竖线；你在左、AI 在右；每个阶段在中轴上一个序号，序号左边阶段名、右边「目标」
// - 「你：」那段（到下一个标签为止）一张卡放左边，「AI：」放右边，虚线连到中轴上的点（你 = 绿点、AI = 灰点）
// - 其他标签（产物、常见坑……）和没标签的段落放在这一阶段末尾、中轴右边那一栏（和「目标」同一栏），不压中轴；中轴从第一阶段贯穿到最后
// - 手机上一栏排下来，卡片左边框区分你和 AI（卡里保留「你：」「AI：」开头）
// 各格内容的切分在 build_guide.py 里做，这里只排版

type StagesBlock = Extract<Block, { type: 'stages' }>

function Row({ me, children }: { me?: boolean; children: ReactNode }) {
  return (
    <div className={`stg-row ${me ? 'me' : 'ai'}`}>
      <div className="stg-c">{me && <div className="stg-card">{children}</div>}</div>
      <div className="stg-ax" aria-hidden="true"><i className="stg-dash" /><i className="stg-dot" /></div>
      <div className="stg-c">{!me && <div className="stg-card">{children}</div>}</div>
    </div>
  )
}

export function Stages({ b, md }: { b: StagesBlock; md: (text: string, inline?: boolean) => ReactNode }) {
  return (
    <>
      {b.intro && md(b.intro)}
      <div className="stg">
        <div className="stg-who" aria-hidden="true">
          <span className="me"><i><User className="size-4" /></i>你</span>
          <span />
          <span className="ai"><i><Bot className="size-4" /></i>AI</span>
        </div>
        <div className="stg-body">
          {b.stages.map((s, i) => (
            <section key={i} className="stg-band">
              <div className="stg-head">
                <h4 className="stg-name">{md(s.name, true)}</h4>
                <span className="stg-n">{i + 1}</span>
                <div className="stg-goal">{s.goal && md(s.goal)}</div>
              </div>
              {s.me && <Row me>{md(s.me)}</Row>}
              {s.ai && <Row>{md(s.ai)}</Row>}
              {s.foot && <div className="stg-row stg-note"><div className="stg-c" /><div className="stg-ax" aria-hidden="true" /><div className="stg-c stg-foot">{md(s.foot)}</div></div>}
            </section>
          ))}
        </div>
      </div>
    </>
  )
}
