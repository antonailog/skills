import { useEffect, useId, useState } from 'react'

/** 跟着 <html data-theme> 变：顶栏切深浅色时图重画 */
function useDark() {
  const get = () => document.documentElement.getAttribute('data-theme') === 'dark'
  const [dark, setDark] = useState(get)
  useEffect(() => {
    const mo = new MutationObserver(() => setDark(get()))
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => mo.disconnect()
  }, [])
  return dark
}

// ```mermaid 代码块画成流程图（白卡细边里居中，宽了按栏宽缩）；mermaid 很大，用到时才加载
let mermaidTheme = ''
export function Flow({ chart }: { chart: string }) {
  const id = useId().replace(/[^a-zA-Z0-9]/g, '')
  const dark = useDark()
  const [svg, setSvg] = useState('')
  useEffect(() => {
    let live = true
    const theme = dark ? 'dark' : 'neutral'
    import('mermaid').then(async ({ default: mermaid }) => {
      if (mermaidTheme !== theme) {
        mermaid.initialize({ startOnLoad: false, theme, fontFamily: 'inherit', themeVariables: { fontSize: '14px', edgeLabelBackground: dark ? '#171717' : '#ffffff' }, flowchart: { curve: 'basis', htmlLabels: true } })
        mermaidTheme = theme
      }
      const { svg } = await mermaid.render(`flow${id}`, chart)
      if (live) setSvg(svg)
    }).catch(() => live && setSvg(''))
    return () => { live = false }
  }, [chart, dark, id])
  return <div className="flex justify-center [&_svg]:h-auto [&_svg]:max-w-full" dangerouslySetInnerHTML={{ __html: svg }} />
}
