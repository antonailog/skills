import type { ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Cite } from '@/components/Cite'
import { sourceOf } from '@/data'

// 正文里的特殊链接（build_guide.py 转出来的）：cite: 引用编号、hl: 荧光笔、ul: 下划线；其余是普通外链（新窗口打开）
export function renderLink(href: string | undefined, children: ReactNode) {
  if (href?.startsWith('cite:')) { const s = sourceOf[href.slice(5)]; return s ? <Cite s={s} /> : null }
  if (href === 'hl:') return <mark>{children}</mark>
  if (href === 'ul:') return <span className="ul">{children}</span>
  if (href?.startsWith('#')) return <a href={href}>{children}</a>
  return <a href={href} target="_blank" rel="noopener">{children}</a>
}

/** 一小段 md（导语）：段落照常，只换特殊链接 */
export function Inline({ md }: { md: string }) {
  return <ReactMarkdown remarkPlugins={[remarkGfm]} urlTransform={(u) => u} components={{ a: ({ href, children }) => renderLink(href, children) }}>{md}</ReactMarkdown>
}
