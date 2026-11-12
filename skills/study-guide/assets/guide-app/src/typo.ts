// 字号：只用博客的 8 档（12 / 13 / 14 / 15 / 17 / 20 / 24 / 32，见 设计规范/tokens.css）；正文标题由 post.css 管，这里只给图和卡片用
export const T = {
  name: 'text-[17px] leading-snug font-semibold text-foreground',   // 卡片里的条目名：比正文（16）高一档、黑字（11-11 卡片审查：原来 15px 灰字，比正文还小）
  num: 'mr-2.5 font-mono text-[13px] font-normal text-[var(--accent-ink)]',   // 条目序号：同目录、章节编号（等宽、深黄绿）
} as const
