import { useState } from 'react'

// 提示词的中英两版：一行「--- en ---」前面是中文、后面是英文原文。默认显示中文，左上角「中文 | English」切换；复制按钮复制当前显示的那一版
const SPLIT = /^[ \t]*---[ \t]*en[ \t]*---[ \t]*$/m

export function useBilingual(text: string) {
  const at = text.search(SPLIT)
  const zh = at < 0 ? text : text.slice(0, at).trim()
  const en = at < 0 ? '' : text.slice(at).replace(SPLIT, '').trim()
  const has = at >= 0 && !!zh && !!en
  const [showEn, setEn] = useState(false)
  const shown = has ? (showEn ? en : zh) : text.trim()
  const bar = has ? (
    <div className="bi-bar" role="group" aria-label="提示词语言">
      <button type="button" aria-pressed={!showEn} onClick={() => setEn(false)}>中文</button>
      <button type="button" aria-pressed={showEn} onClick={() => setEn(true)}>English</button>
    </div>
  ) : null
  return { has, shown, bar }
}
