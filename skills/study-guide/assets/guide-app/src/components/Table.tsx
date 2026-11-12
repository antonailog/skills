import { Children, cloneElement, isValidElement, useLayoutEffect, useRef, useState, type CSSProperties, type ReactElement, type ReactNode } from 'react'
import { text } from '@/components/TableCards'

/*
 * 正文表格：按内容算列宽，让表格总高度最小（表格自动排版研究里的标准目标，见 references/components.md「表格」）。
 *
 * 1. 量（只量一次，自然宽度不随栏宽变）：每个格子排成一行的宽度、每列最长的不可断开片段（英文单词、网址）、每列内边距。
 * 2. 全表一行放得下：都不换行，表格按内容宽，不撑满整栏。
 * 3. 短列：一列最长的格子不超过 SHORT 个字宽，整列不换行，宽度就是它的自然宽度（标签、数字、短语）。
 * 4. 长列分剩下的宽度：枚举各长列之间的分法，估算每行折成几行，挑所有行加起来最矮的那种；
 *    估算按「自然宽度 ÷ 列宽」算，英文按整词换行时会估少，所以取估算最好的几种，在隐藏的副本上按真实排版各量一次，取实际最矮的。
 *    每列不窄于下限：最长片段、表头前 8 个字宽、5 个字宽。
 * 5. 最常见的行高超过 MAXL 行（或下限加起来就放不下）：表格依次加宽到 1.2、1.4 倍栏宽，取第一个放得下的，
 *    横向滚动，首列固定（首列本身超过栏宽四成时不固定），右边缘渐隐提示还有内容。加宽到 1.4 倍还放不下，改排成行块
 *    （句子太多，横着读比竖着读累）。全是短列、合起来超出栏宽的表（多为数字表）不换行，直接横滑。
 * 6. 排好后：折了行、最后一行不超过 3 个字的格子改用均衡断行（行数不变、不留孤字）；数字和单位不拆开（「10 月」「45 ms」）。
 * 测量和复核都在副本上做，不动页面上的表；字体加载完重量一次；窗口宽度变化 8px 以上才重排，一帧最多一次。
 */
const SHORT = 10   // 字宽（em）
const MAXL = 3

type El = ReactElement<{ children?: ReactNode; href?: string }>

/* ---------- 文字处理 ---------- */

const isCite = (x: unknown) => isValidElement(x) && typeof (x as El).props.href === 'string' && ((x as El).props.href as string).startsWith('cite:')

/** 引用编号和它前面那个字（或那个英文词、标点）粘在一起，不单独掉到下一行 */
export function glueCites(children: ReactNode): ReactNode {
  const arr = Children.toArray(children)
  if (!arr.some(isCite)) return children
  const out: ReactNode[] = []
  let i = 0
  while (i < arr.length) {
    if (!isCite(arr[i])) { out.push(arr[i++]); continue }
    const run: ReactNode[] = []
    while (i < arr.length && isCite(arr[i])) run.push(arr[i++])
    const prev = out[out.length - 1]
    let lead = ''
    if (typeof prev === 'string') {
      const m = prev.match(/(?:[㐀-鿿　-〿＀-￯][)）」』"”。，、；：！？]*|[^\s㐀-鿿　-〿＀-￯]{1,24})\s*$/)
      if (m) { lead = m[0]; out[out.length - 1] = prev.slice(0, -lead.length) }
    } else if (prev !== undefined) lead = '\u2060'   // 前面是高亮、加粗、链接这类元素：插一个不断行符，不把整个元素包进不换行
    out.push(<span key={`g${i}`} className="nw">{lead}{run}</span>)
  }
  return out
}

/** 数字和后面的单位不拆开：数字后的空格换成不换行空格 */
function keepUnits(n: ReactNode): ReactNode {
  return Children.map(n, (c) => {
    if (typeof c === 'string') return c.replace(/(\d) (?=[\u4e00-\u9fff%]|(?:ms|s|fps|px|BPM|bpm|dB|LUFS|Hz|kHz|KB|MB|GB|TB|K|M)\b)/g, '$1\u00a0')
    if (isValidElement(c) && typeof c.type === 'string' && c.type !== 'code' && (c as El).props.children !== undefined)
      return cloneElement(c as El, undefined, keepUnits((c as El).props.children))
    return c
  })
}

/* ---------- 表格分类 ---------- */

const NUMERIC = /^[\s\d.,%+\-–—~～×x:：/·]*(秒|帧|字|px|倍|ms|s|fps|%|个|分钟|BPM|LUFS|dB)?[\s\d.,%+\-–—~～×x:：/·]*$/i
const clean = (c: ReactNode) => text(c).trim()

/** 数字列：右对齐 */
const numericCols = (head: ReactNode[], rows: ReactNode[][]) => head.map((_, k) => rows.length > 0 && rows.every((r) => { const t = clean(r[k]); return t && NUMERIC.test(t) }))

/** 句子多的表：至少两列（首列除外）平均超过 10 个字。手机上一行放不下两列句子，这种表在手机上排成行块 */
export function textHeavy(head: ReactNode[], rows: ReactNode[][]) {
  return head.slice(1).filter((_, j) => rows.reduce((a, r) => a + [...clean(r[j + 1])].length, 0) / Math.max(rows.length, 1) > 10).length >= 2
}

/** 行块：左边行标签，右边各字段「表头：内容」一行一个 */
export function RowBlocks({ head, rows }: { head: ReactNode[]; rows: ReactNode[][] }) {
  const dt = Math.min(8, Math.max(2, ...head.slice(1).map((h) => [...text(h)].reduce((a, c) => a + (/[㐀-鿿]/.test(c) ? 1 : 0.55), 0)))) + 0.5
  return (
    <div className="rb" style={{ '--dt': `${dt}em` } as CSSProperties}>
      {rows.map((r, i) => (
        <div key={i} className="rb-row">
          <div className="rb-h">{r[0]}</div>
          <dl className="rb-f">{r.slice(1).map((c, k) => <div key={k}><dt>{head[k + 1]}</dt><dd>{glueCites(keepUnits(c))}</dd></div>)}</dl>
        </div>
      ))}
    </div>
  )
}

/* ---------- 列宽 ---------- */

type Plan = { mode: 'fit' | 'fixed' | 'scroll' | 'blocks'; cols: number[]; width: number; nowrap: boolean[] }
type Meas = { em: number; nat: number[][]; minc: number[]; pad: number[] }

/** 页面上那张表的副本：去掉列宽、均衡断行和行内样式，放进一个同样带 .tbl 的隐形容器（表格样式才一致），
 *  挂在可见的外层容器里（绝对定位、不可见），量完连容器一起删 */
function cloneOf(t: HTMLTableElement, host: HTMLElement) {
  const c = t.cloneNode(true) as HTMLTableElement
  c.querySelector('colgroup')?.remove()
  c.querySelectorAll('.bal').forEach((e) => e.classList.remove('bal'))
  c.removeAttribute('style')
  const holder = document.createElement('div')
  holder.className = 'tbl'
  holder.style.cssText = 'position:absolute;left:0;top:0;width:100%;overflow:visible;visibility:hidden;pointer-events:none'
  holder.appendChild(c)
  host.appendChild(holder)
  return c
}
const drop = (c: HTMLTableElement) => c.parentElement?.remove()

function measure(t: HTMLTableElement, host: HTMLElement): Meas | null {
  const c = cloneOf(t, host)
  try {
    const em = parseFloat(getComputedStyle(c).fontSize)
    const rows = [...c.rows]
    const n = rows[0].cells.length
    const own = (x: HTMLElement) => { const r = document.createRange(); r.selectNodeContents(x); return r.getBoundingClientRect().width }
    c.classList.add('m-nat')   // 整表不换行：每格的自然宽度
    const nat = rows.map((r) => [...r.cells].map(own))
    c.classList.replace('m-nat', 'm-min')   // 整表按最小内容宽排：每列最长的不可断开片段
    const minc = [...rows[0].cells].map((x) => { const cs = getComputedStyle(x); return x.getBoundingClientRect().width - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight) })
    const pad = [...Array(n)].map((_, k) => Math.max(...rows.map((r) => { const cs = getComputedStyle(r.cells[k]); return parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight) })))
    return nat.flat().some((w) => w > 0) ? { em, nat, minc, pad } : null   // 全是 0：容器还没显示出来，算测量失败
  } finally { drop(c) }
}

/** 一种行高分布的得分：所有行加起来越矮越好；一样矮时，最常见行高占比高的好。L 是最常见的行高 */
function rate(R: number[]) {
  if (!R.length) return { L: 1, s: 0 }
  const cnt = new Map<number, number>()
  R.forEach((v) => cnt.set(v, (cnt.get(v) ?? 0) + 1))
  let L = 1, top = 0
  cnt.forEach((c, v) => { if (c > top || (c === top && v < L)) { top = c; L = v } })
  return { L, s: -R.reduce((a, b) => a + b, 0) / R.length + 0.01 * top / R.length }
}

/** 预算是 f 倍栏宽时的分法：返回估算最好的几种候选（各列宽度含内边距） */
function plan({ em, nat, minc, pad }: Meas, C: number, f = 1): Plan & { cands: number[][] } {
  const n = minc.length
  const body = nat.slice(1), head = nat[0]
  const W = [...Array(n)].map((_, k) => Math.max(...body.map((r) => r[k])))
  const short = W.map((w, k) => w <= SHORT * em && head[k] <= SHORT * em)
  const padSum = pad.reduce((a, b) => a + b, 0)
  const natTotal = W.reduce((s, w, k) => s + Math.max(w, head[k]), 0) + padSum
  if (natTotal <= C) return { mode: 'fit', cols: [], width: natTotal, nowrap: W.map(() => true), cands: [] }

  const longIdx = W.map((_, k) => k).filter((k) => !short[k])
  const cols = W.map((w, k) => (short[k] ? Math.max(w, head[k]) : 0))
  if (!longIdx.length) {   // 全是短列、合起来超出栏宽：都不换行，横向滚动
    const full = cols.map((c, k) => c + pad[k])
    return { mode: 'scroll', cols: full, width: full.reduce((a, b) => a + b, 0), nowrap: short, cands: [] }
  }
  const A = C * f - padSum - cols.reduce((a, b) => a + b, 0)
  const lo = longIdx.map((k) => Math.max(minc[k], Math.min(head[k], 8 * em), 5 * em))
  const loSum = lo.reduce((a, b) => a + b, 0)
  const mode: Plan['mode'] = f > 1 ? 'scroll' : 'fixed'
  if (A < loSum) return { mode, cols: [], width: 0, nowrap: short, cands: [] }

  const lines = (w: number, x: number) => Math.max(1, Math.ceil((w - 0.3 * em) / x))
  const score = (x: number[]) => rate(body.map((r) => Math.max(1, ...longIdx.map((k, i) => lines(r[k], x[i])))))
  // 逐列枚举宽度（最后一列拿剩下的），步长按列数放粗，计算量保持在几万次以内
  const m = longIdx.length
  const k = Math.min(120, Math.floor(Math.pow(20000, 1 / Math.max(1, m - 1))))   // 每列试 k 种宽度，组合总数不超过约 2 万
  const step = Math.max(0.5 * em, A / Math.max(2, k))
  const top: { x: number[]; s: number }[] = []
  const rec = (i: number, rest: number, acc: number[]) => {
    if (i === m - 1) {
      if (rest < lo[i]) return
      const x = [...acc, rest]
      const r = score(x)
      if (r.L <= MAXL) { top.push({ x, s: r.s }); if (top.length > 400) { top.sort((a, b) => b.s - a.s); top.length = 40 } }
      return
    }
    for (let v = lo[i]; v <= rest - lo.slice(i + 1).reduce((a, b) => a + b, 0) + 1e-6; v += step) rec(i + 1, rest - v, [...acc, v])
  }
  rec(0, A, [])
  top.sort((a, b) => b.s - a.s)
  const toCols = (x: number[]) => { const c = [...cols]; longIdx.forEach((k, i) => { c[k] = x[i] }); return c.map((v, k) => v + pad[k]) }
  // 估算得分相近的多半是相邻的分法：彼此差一个字宽以上才算不同的候选，取 8 种交给真实排版复核
  const cands: number[][] = []
  for (const t of top) { if (cands.length >= 8) break; const c = toCols(t.x); if (cands.every((o) => o.some((v, k) => Math.abs(v - c[k]) > em))) cands.push(c) }
  return { mode, cols: cands[0] ?? [], width: 0, nowrap: short, cands }
}

/** 一个格子实际排成的各行（左右边界） */
function linesOf(c: HTMLElement) {
  const r = document.createRange(); r.selectNodeContents(c)
  const lines: { y: number; l: number; r: number }[] = []
  for (const x of r.getClientRects()) {
    if (x.width < 0.5) continue
    const ln = lines.find((v) => Math.abs(v.y - x.top) < 4)
    if (ln) { ln.l = Math.min(ln.l, x.left); ln.r = Math.max(ln.r, x.right) } else lines.push({ y: x.top, l: x.left, r: x.right })
  }
  return lines.sort((a, b) => a.y - b.y)
}

/** 在副本上套每种候选列宽，按真实排版打分，返回最好的一种和它最常见的行高 */
function verify(t: HTMLTableElement, host: HTMLElement, cands: number[][], nowrap: boolean[]) {
  const c = cloneOf(t, host)
  const cg = document.createElement('colgroup')
  nowrap.forEach(() => cg.appendChild(document.createElement('col')))
  c.insertBefore(cg, c.firstChild)
  c.style.tableLayout = 'fixed'
  ;[...c.rows].forEach((r) => [...r.cells].forEach((cell, k) => { cell.style.whiteSpace = nowrap[k] ? 'nowrap' : 'normal' }))
  let best = cands[0], bestS = -Infinity, bestL = 99
  try {
    for (const cd of cands) {
      cd.forEach((w, k) => { (cg.children[k] as HTMLElement).style.width = `${w}px` })
      c.style.width = `${cd.reduce((a, b) => a + b, 0)}px`
      const lines = [...c.tBodies[0].rows].map((row) => Math.max(...[...row.cells].map((cell) => linesOf(cell).length)))
      if (lines.every((v) => v === 0)) return { cols: best, L: 99 }   // 什么都量不到：容器没显示出来，按失败处理
      const r = rate(lines.map((v) => Math.max(1, v)))
      const sc = r.L > MAXL ? -99 : r.s
      if (sc > bestS + 1e-9) { bestS = sc; best = cd; bestL = r.L }
    }
  } finally { drop(c) }
  return { cols: best, L: bestL }
}

/** 折了行、最后一行不超过 3 个字的格子：均衡断行 */
function balanceOrphans(t: HTMLTableElement) {
  const em = parseFloat(getComputedStyle(t).fontSize)
  t.querySelectorAll('td').forEach((c) => {
    c.classList.remove('bal')
    const lines = linesOf(c)
    if (lines.length > 1 && lines[lines.length - 1].r - lines[lines.length - 1].l < 3.5 * em) c.classList.add('bal')
  })
}

/** 按栏宽 C 选排法：一行放得下 → 按内容宽；放得进整栏 → 定宽；否则加宽到 1.2、1.4 倍横滑；还放不下 → 行块 */
function choose(m: Meas, t: HTMLTableElement, host: HTMLElement, C: number): Plan {
  for (const f of [1, 1.2, 1.4]) {
    const q = plan(m, C, f)
    if (q.mode === 'fit' || (q.mode === 'scroll' && !q.cands.length && q.cols.length)) return q   // 一行放得下；或全是短列，直接横滑
    if (!q.cands.length) continue
    const v = verify(t, host, q.cands, q.nowrap)
    if (v.L <= MAXL) return { mode: q.mode, cols: v.cols, width: v.cols.reduce((a, b) => a + b, 0), nowrap: q.nowrap }
  }
  return { mode: 'blocks', cols: [], width: 0, nowrap: [] }
}

/** 正文表格 */
export function FitTable({ head, rows }: { head: ReactNode[]; rows: ReactNode[][] }) {
  const num = numericCols(head, rows)
  const ref = useRef<HTMLTableElement>(null)
  const box = useRef<HTMLDivElement>(null)
  const wrap = useRef<HTMLDivElement>(null)
  const [p, setP] = useState<Plan | null>(null)
  const [edge, setEdge] = useState({ l: false, r: false })

  useLayoutEffect(() => {
    const t = ref.current, o = wrap.current
    if (!t || !o || !rows.length) return   // 只有表头的表不排
    let m: Meas | null = null, w = 0, frame = 0
    const run = () => {
      frame = 0
      const C = Math.floor(o.getBoundingClientRect().width) - 1   // 留 1px，避免取整后多出一条横向滚动条
      if (C <= 0 || !ref.current || Math.abs(C - w) < 8) return   // 藏起来时（比如手机上的宽屏版）不量；宽度变化不到 8px 不重排
      if (!m) m = measure(ref.current, o)
      if (!m) return
      w = C
      setP(choose(m, ref.current, o, C))
    }
    const later = () => { if (!frame) frame = requestAnimationFrame(run) }
    const remeasure = () => { m = null; w = 0; later() }   // 字体到了，字宽会变：重量
    run()
    document.fonts?.ready.then(remeasure)
    document.fonts?.addEventListener?.('loadingdone', remeasure)
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(later) : null
    ro?.observe(o)
    return () => { ro?.disconnect(); document.fonts?.removeEventListener?.('loadingdone', remeasure); if (frame) cancelAnimationFrame(frame) }
  }, [rows.length])

  useLayoutEffect(() => {
    const t = ref.current, b = box.current
    if (!t || !b || !p) return
    if (p.mode === 'blocks') { setEdge({ l: false, r: false }); return }
    balanceOrphans(t)
    const upd = () => setEdge({ l: b.scrollLeft > 2, r: b.scrollLeft + b.clientWidth < b.scrollWidth - 2 })
    upd()
    b.addEventListener('scroll', upd, { passive: true })
    return () => b.removeEventListener('scroll', upd)
  }, [p])

  const cls = (k: number) => [num[k] && k > 0 ? 'num' : '', p?.nowrap[k] ? 'nw' : ''].filter(Boolean).join(' ') || undefined
  const sized = !!p && (p.mode === 'fixed' || p.mode === 'scroll') && p.cols.length > 0
  // 首列固定：首列本身超过栏宽四成时不固定，免得手机上占掉大半屏
  const stick = p?.mode === 'scroll' && (p.cols[0] ?? 0) <= 0.4 * (wrap.current?.clientWidth ?? Infinity)
  return (
    <div ref={wrap} className={`fit-wrap${p?.mode === 'scroll' ? ' scroll' : ''}${stick ? ' stick' : ''}${edge.l ? ' at-l' : ''}${edge.r ? ' at-r' : ''}`}>
      {p?.mode === 'blocks' && <RowBlocks head={head} rows={rows} />}
      <div className="tbl" ref={box} hidden={p?.mode === 'blocks'}>
        <table ref={ref} className={`tbl-a fit-${p?.mode ?? 'auto'}`} style={sized ? { tableLayout: 'fixed', width: p.mode === 'fixed' ? '100%' : p.width } : undefined}>
          {sized && <colgroup>{p.cols.map((c, k) => <col key={k} style={{ width: p.mode === 'fixed' ? `${(c / p.width) * 100}%` : c }} />)}</colgroup>}
          <thead><tr>{head.map((h, k) => <th key={k} className={cls(k)}>{h}</th>)}</tr></thead>
          <tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, k) => <td key={k} className={cls(k)}>{glueCites(keepUnits(c))}</td>)}</tr>)}</tbody>
        </table>
      </div>
    </div>
  )
}
