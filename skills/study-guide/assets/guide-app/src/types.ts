// 页面数据的形状：scripts/build_guide.py 从学习指南目录生成 src/gen/guide.json

/** sources.json 的一条，n 是正文里第一次出现的顺序 */
export type Source = { n: number; id: string; title: string | null; url: string | null; site: string | null; date: string | null; icon: string | null }

/** 章（level 2）带 n（两位编号，没编号的章为 null）和 title（去掉「一、」的标题） */
export type Head = { line: number; level: number; text: string; id: string; n?: string | null; title?: string }

/** sites.json：截图在 img/sites/<img>.jpg（img 里带 / 时按学习指南目录下的相对路径取，如 img/refs/x.jpg）；没有 img 的只给链接。
 *  meta：一行关键信息（年份、出处、获奖、数据，要有出处）；desc：一句话说明它在文中为什么值得看
 *  shot：只给 collect_refs.py 截图用，页面不读。wait：页面加载完再等的毫秒数（有加载动画时给 4000–8000）；
 *  scroll：截图前滚到的 CSS 选择器，或往下滚的像素数 */
export type Site = { key: string; name: string; url: string; img?: string | null; meta?: string; desc?: string; shot?: { wait?: number; scroll?: string | number } }

/** videos.json：mp4 / youtube 能嵌就嵌，都没有就是封面卡、点了开 url */
export type Video = { name: string; url?: string | null; poster?: string | null; mp4?: string | null; youtube?: string | null }

/** 中轴两栏的一个阶段：每格是一段 markdown */
export type Stage = { name: string; goal: string; me: string; ai: string; foot: string }

export type Block =
  | { type: 'gallery'; keys: string[] }
  | { type: 'video'; names: string[] }
  | { type: 'stages'; intro: string; stages: Stage[] }

export type Guide = {
  title: string
  /** 标题和第一章之间的段落 */
  lede: string
  date: string
  minutes: number
  back: { href: string; label: string } | null
  md: string
  heads: Head[]
  /** 来源列表在目录里的位置：parent = 挂在哪一章（「其他」）下；n = 自成一章时的编号 */
  refs: { parent?: string; n?: string } | null
  sources: Source[]
  sites: Record<string, Site>
  videos: Record<string, Video>
  /** 正文里的 [blk](blk:N) 对应这里第 N 个 */
  blocks: Block[]
}
