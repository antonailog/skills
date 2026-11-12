import type { ReactNode } from 'react'
import { PaceDemo } from './Pace'

// guide.md 里 ::fig <名字> 对应的组件：新演示写在本目录，在这里登记名字（build_guide.py 按这张表查名字，写错报行号）
export const FIGURES: Record<string, () => ReactNode> = {
  pace: PaceDemo,
}
