import { isValidElement, memo, type ReactElement, type ReactNode } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { TableCards, parseTable, wantCards } from '@/components/TableCards'
import { FitTable, RowBlocks, glueCites, textHeavy } from '@/components/Table'
import { MediaGroup } from '@/components/Media'
import { Gallery } from '@/components/Gallery'
import { Stages } from '@/components/Stages'
import { Flow } from '@/components/Flow'
import { Say } from '@/components/Say'
import { CopyBtn } from '@/components/CopyBtn'
import { ZoomFig } from '@/components/ZoomFig'
import { renderLink } from '@/components/Md'
import { FIGURES } from '@/figures'
import { guide } from '@/data'

// 正文：标签和类名照文章页（h2.sec + .hn 编号、h3.sub、.hash 复制链接、pre + .copy），样式来自 post.css 和 index.css
// build_guide.py 把特殊写法转成了占位链接：[fig](fig:名字)、[blk](blk:N)（画廊、视频、中轴两栏）、cite: / hl: / ul:

type HNode = { type: string; tagName?: string; value?: string; properties?: { href?: string; src?: string; alt?: string }; children?: HNode[]; position?: { start: { line: number } } }

let toastTimer = 0
function toast(msg: string) {
  let el = document.querySelector<HTMLDivElement>('.toast')
  if (!el) { el = document.createElement('div'); el.className = 'toast'; el.setAttribute('role', 'status'); document.body.appendChild(el) }
  el.textContent = msg
  el.classList.add('show')
  clearTimeout(toastTimer)
  toastTimer = window.setTimeout(() => el!.classList.remove('show'), 1600)
}
const copyText = (t: string, msg: string) => navigator.clipboard?.writeText(t).then(() => toast(msg), () => toast('复制失败'))

export function Hash({ id }: { id?: string }) {
  if (!id) return null
  return <a className="hash" href={`#${id}`} aria-label="复制这一节的链接" onClick={() => copyText(`${location.href.split('#')[0]}#${id}`, '已复制这一节的链接')}>#</a>
}

/** 代码块：mermaid 画成流程图；prompt 是提示词块（浅强调色底、复制、中英切换）；其他是浅灰底细边、悬停出「复制」，不做语法高亮 */
function Block({ children }: { children: ReactNode }) {
  const code = isValidElement(children) ? children as ReactElement<{ className?: string; children?: ReactNode }> : null
  const text = String(code?.props.children ?? '').replace(/\n$/, '')
  const lang = code?.props.className?.replace(/^language-/, '')
  if (lang === 'mermaid') return <div className="fig-box"><div className="fig-panel"><Flow chart={text} /></div></div>
  if (lang === 'prompt') return <Say t={text} />
  return (
    <pre>
      <code>{text}</code>
      <CopyBtn className="copy" text={text} />
    </pre>
  )
}

const solo = (node?: HNode) => {
  const kids = (node?.children ?? []).filter((c) => !(c.type === 'text' && !c.value?.trim()))
  return kids.length === 1 ? kids[0] : null
}

/** 一段只有一个占位链接 → 换成演示、画廊、视频、中轴两栏；只有一张图 → 白框放大图 */
function blockOf(node?: HNode): ReactNode | null {
  const k = solo(node)
  if (k?.tagName === 'img' && k.properties?.src) return <ZoomFig src={k.properties.src} alt={k.properties.alt ?? ''} />
  if (k?.tagName !== 'a') return null
  const href = k.properties?.href ?? ''
  if (href.startsWith('fig:')) { const F = FIGURES[href.slice(4)]; return F ? <F /> : null }
  if (!href.startsWith('blk:')) return null
  const b = guide.blocks[Number(href.slice(4))]
  if (b?.type === 'gallery') return <Gallery keys={b.keys} />
  if (b?.type === 'video') return <MediaGroup items={b.names.map((n) => guide.videos[n]).filter(Boolean)} />
  if (b?.type === 'stages') return <Stages b={b} md={(t, inline) => <Sub md={t} inline={inline} />} />
  return null
}

function textOf(n?: HNode): string { return !n ? '' : n.type === 'text' ? n.value ?? '' : (n.children ?? []).map(textOf).join('') }

const shared: Components = {
  h4: ({ children }) => <h4>{children}</h4>,
  p: ({ node, children }) => blockOf(node as HNode) ?? <p>{glueCites(children)}</p>,
  li: ({ children }) => <li>{glueCites(children)}</li>,
  pre: ({ children }) => <Block>{children}</Block>,
  // 表格：5 列以上的长句表 → 卡片；句子多的表在手机上排成行块；其余按内容算列宽（components/Table.tsx）
  table: ({ children }) => {
    const t = parseTable(children)
    if (wantCards(t.head, t.rows)) return <TableCards {...t} />
    return textHeavy(t.head, t.rows)
      ? <><div className="only-wide"><FitTable {...t} /></div><div className="only-narrow"><RowBlocks {...t} /></div></>
      : <FitTable {...t} />
  },
  a: ({ href, children }) => renderLink(href, children),
}

/** 中轴两栏格子里的一段 md：同一套组件，标题不挂锚点 */
function Sub({ md, inline }: { md: string; inline?: boolean }) {
  const comps = inline ? { ...shared, p: ({ children }: { children?: ReactNode }) => <>{children}</> } : shared
  return <ReactMarkdown remarkPlugins={[remarkGfm]} urlTransform={(u) => u} components={comps}>{md}</ReactMarkdown>
}

export const GuideBody = memo(function GuideBody() {
  const byLine = new Map(guide.heads.map((h) => [h.line, h]))
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      urlTransform={(u) => u}
      components={{
        ...shared,
        h2: ({ node }) => {
          const h = byLine.get((node as HNode)?.position?.start.line ?? -1)
          return <h2 id={h?.id} className="sec">{h?.n && <span className="hn" aria-hidden="true">{h.n}</span>}<span className="ht">{h?.title ?? textOf(node as HNode)}</span><Hash id={h?.id} /></h2>
        },
        h3: ({ node, children }) => {
          const h = byLine.get((node as HNode)?.position?.start.line ?? -1)
          return <h3 id={h?.id} className="sub"><span className="ht">{children}</span><Hash id={h?.id} /></h3>
        },
      }}
    >{guide.md}</ReactMarkdown>
  )
})
