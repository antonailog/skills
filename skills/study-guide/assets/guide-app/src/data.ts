import raw from '@/gen/guide.json?raw'
import type { Guide, Source } from '@/types'

// 页面数据：scripts/build_guide.py 从学习指南目录的 guide.md、sources.json 等生成

export const guide = JSON.parse(raw) as Guide
export const sourceOf: Record<string, Source> = Object.fromEntries(guide.sources.map((s) => [s.id, s]))
