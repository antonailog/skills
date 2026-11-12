import fs from 'node:fs'
import path from 'node:path'
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { viteSingleFile } from 'vite-plugin-singlefile'

// 两种构建（主题文件夹 = 环境变量 GUIDE_DIR，相对本目录，默认上一层；scripts/build_guide.py 用同一条规则）：
// · npm run build       单个 index.html（双击就能开），拷到 <主题>/index.html，和 img/ 同级
// · npm run build:blog  拆成小文件到 <主题>/site/（html + js + css，img/ 一起拷），发到博客：图片单独成文件、脚本小
const TOPIC = path.resolve(__dirname, process.env.GUIDE_DIR || '..')
const SITE_OUT = path.join(TOPIC, 'site')

type Link = { label: string; href: string; current?: boolean }
type Shell = {
  lang?: string; title: string; ogTitle: string; description: string; favicon?: string; stylesheets?: string[]
  siteName?: string; siteHref?: string; nav?: Link[]; github?: string; footer?: Link | null; themeKey?: string
}

const esc = (s: unknown = '') => String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
const GH = '<svg viewBox="0 0 16 16" aria-hidden="true" style="fill:currentColor;stroke:none"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>'
const THEME_BTN = `<button class="icon-btn" id="theme" type="button" aria-label="切换深浅色" title="切换深浅色">
      <svg class="i-sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M6.3 17.7l-1.4 1.4M19.1 4.9l-1.4 1.4"/></svg>
      <svg class="i-moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>
    </button>`

/** index.html 里的 __xx__：标题、描述、顶栏、页脚，按 src/gen/shell.json（build_guide.py 从 site.config.json 和 guide.md 生成）写成静态 HTML */
function shell(): Plugin {
  return {
    name: 'guide-shell',
    transformIndexHtml: {
      order: 'pre',
      handler(html) {
        const s: Shell = JSON.parse(fs.readFileSync(path.resolve(__dirname, 'src/gen/shell.json'), 'utf8'))
        const css = s.stylesheets ?? []
        const head = [
          s.favicon ? `<link rel="icon" href="${esc(s.favicon)}">` : '',
          ...(css.some((u) => u.startsWith('https://fonts.googleapis.com')) ? ['<link rel="preconnect" href="https://fonts.googleapis.com">', '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'] : []),
          ...css.map((u) => `<link rel="stylesheet" href="${esc(u)}">`),
        ].filter(Boolean).join('\n')
        const nav = (s.nav ?? []).map((n) => `<a${n.current ? ' class="on" aria-current="page"' : ''} href="${esc(n.href)}">${esc(n.label)}</a>`).join('')
        const gh = s.github ? `<a class="icon-btn" href="${esc(s.github)}" target="_blank" rel="noopener" aria-label="GitHub" title="GitHub">${GH}</a>` : ''
        const topbar = `<header class="topbar">
  <a class="brand" href="${esc(s.siteHref ?? '/')}">${esc(s.siteName)}</a>
  <nav class="nav" aria-label="主导航">${nav}</nav>
  <div class="tb-act">${gh}${THEME_BTN}</div>
</header>`
        const footer = s.footer ? `<footer class="foot"><a href="${esc(s.footer.href)}">${esc(s.footer.label)}</a></footer>` : ''
        const map: Record<string, string> = {
          __LANG__: esc(s.lang ?? 'zh-CN'), __TITLE__: esc(s.title), __OG_TITLE__: esc(s.ogTitle), __DESC__: esc(s.description),
          __THEME_KEY__: esc(s.themeKey ?? 'theme'), __HEAD__: head, __TOPBAR__: topbar, __FOOTER__: footer,
        }
        return html.replace(/__[A-Z_]+__/g, (k) => map[k] ?? k)
      },
    },
  }
}

/** 博客版：主题文件夹的 img/ 拷进 site/；单文件版：dist/index.html 拷到主题文件夹 */
function output(mode: string): Plugin {
  return {
    name: 'guide-output',
    apply: 'build',
    closeBundle() {
      if (mode === 'blog') {
        const img = path.join(TOPIC, 'img')
        if (fs.existsSync(img)) fs.cpSync(img, path.join(SITE_OUT, 'img'), { recursive: true })
      } else {
        fs.copyFileSync(path.resolve(__dirname, 'dist/index.html'), path.join(TOPIC, 'index.html'))
      }
    },
  }
}

export default defineConfig(({ command, mode }) => ({
  base: './',
  publicDir: command === 'serve' ? TOPIC : false,   // 开发时直接用主题文件夹里的 img/
  plugins: [shell(), react(), tailwindcss(), ...(mode === 'blog' ? [] : [viteSingleFile()]), output(mode)],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  build: mode === 'blog'
    ? { outDir: SITE_OUT, emptyOutDir: true, assetsInlineLimit: 0, assetsDir: 'assets' }
    : {},
}))
