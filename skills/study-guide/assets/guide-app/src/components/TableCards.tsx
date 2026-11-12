import { Children, isValidElement, type ReactElement, type ReactNode } from 'react'
import { T } from '@/typo'
import { Say } from '@/components/Say'

// 宽表格（5 列以上、格子里多是整句话）→ 一行一条卡片，内容一字不删。文档式：标题放在卡外当小标题，字段排成「左标签、右内容」的规格行，标签就是表头原文
// - 第一列当标题；第一列是很短的序号 → 序号 + 第二列合成标题；第一列有重复值 → 按它分组、标题取第二列
// - 整格只有一段行内代码的字段 → 提示词块（带复制），挪到第二行

type El = ReactElement<{ children?: ReactNode }>
const kids = (e: unknown): El[] => isValidElement(e) ? Children.toArray((e as El).props.children).filter(isValidElement) as El[] : []
export const text = (n: ReactNode): string => typeof n === 'string' || typeof n === 'number' ? String(n)
  : Array.isArray(n) ? n.map(text).join('') : isValidElement(n) ? text((n as El).props.children) : ''

export function parseTable(children: ReactNode) {
  const [thead, tbody] = Children.toArray(children).filter(isValidElement)
  const head = kids(kids(thead)[0]).map((th) => th.props.children)
  const rows = kids(tbody).map((tr) => kids(tr).map((td) => td.props.children))
  return { head, rows }
}

/** 序号：1、①、一、A1 这类（2–3 字的中文名不算） */
const ORDINAL = /^(\d{1,3}|[①-⑳]|[一二三四五六七八九十]{1,3}|[A-Za-z]\d{0,2})[.、)]?$/

/** 格子里只有一段行内代码 → 返回代码文字，否则 null */
function codeOnly(c: ReactNode): string | null {
  const arr = Children.toArray(c).filter((x) => !(typeof x === 'string' && !x.trim()))
  return arr.length === 1 && isValidElement(arr[0]) && (arr[0] as El).type === 'code' ? text(arr[0]) : null
}

/** 要不要改成卡片：5 列以上，而且至少 2 列的格子平均超过 16 字（只看长列：「首选 / 少用」这类短值列不拉低判断；数字为主的表保持表格）。
 *  scripts/build_guide.py 的 wants_cards 用同一条规则，两处一起改 */
export function wantCards(head: ReactNode[], rows: ReactNode[][]) {
  if (head.length < 5) return false
  const long = head.filter((_, k) => rows.reduce((a, r) => a + text(r[k]).length, 0) / Math.max(rows.length, 1) > 16).length
  return long >= 2
}

export function TableCards({ head, rows }: { head: ReactNode[]; rows: ReactNode[][] }) {
  const first = rows.map((r) => text(r[0]).trim())
  const grouped = new Set(first).size < rows.length
  const ordinal = !grouped && first.every((t) => ORDINAL.test(t))
  const skip = grouped || ordinal ? 2 : 1
  const titleOf = (r: ReactNode[]) => grouped ? r[1] : ordinal ? <><span className={T.num}>{r[0]}</span>{r[1]}</> : r[0]

  const card = (r: ReactNode[], i: number) => {
    const fields = r.slice(skip).map((c, k) => ({ h: head[k + skip], c, say: codeOnly(c) }))
    const s = fields.findIndex((f) => f.say)
    if (s > 1) fields.splice(1, 0, ...fields.splice(s, 1))
    return (
      <article key={i} className="tc">
        <h4 className={`tc-t ${T.name}`}>{titleOf(r)}</h4>
        <dl className="tc-rows">
          {fields.map((f, k) => (
            <div key={k} className="tc-row">
              <dt>{f.h}</dt>
              <dd>{f.say ? <Say t={f.say} /> : f.c}</dd>
            </div>
          ))}
        </dl>
      </article>
    )
  }

  if (!grouped) return <div className="tcs">{rows.map(card)}</div>
  const groups: { name: string; label: ReactNode; items: { r: ReactNode[]; i: number }[] }[] = []
  rows.forEach((r, i) => {
    const g = groups.at(-1)
    if (g && g.name === first[i]) g.items.push({ r, i })
    else groups.push({ name: first[i], label: r[0], items: [{ r, i }] })
  })
  return (
    <div className="tcs">
      {groups.map((g, gi) => (
        <section key={gi} className="tc-group">
          <p className="tc-gl">{head[0]}：{g.label}</p>
          {g.items.map(({ r, i }) => card(r, i))}
        </section>
      ))}
    </div>
  )
}
