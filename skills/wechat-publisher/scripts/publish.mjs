#!/usr/bin/env node
/**
 * publish.mjs - 注册自定义主题 + 渲染 Markdown + 发布到微信草稿箱
 *
 * 用法:
 *   node publish.mjs <md_file> <theme_ids>
 *
 * 示例:
 *   node publish.mjs ./article_发布版.md sunset-glow
 *   node publish.mjs ./article_发布版.md sunset-glow,ink-bamboo,starry-geek
 *
 * 参数:
 *   md_file   - Markdown 文件路径（带 frontmatter）
 *   theme_ids - 逗号分隔的主题 ID 列表
 *
 * 自定义主题 ID:
 *   sunset-glow  - 落日晚霞（暖橙红渐变）
 *   ink-bamboo   - 墨竹清韵（中国风水墨绿）
 *   starry-geek  - 星空极客（深色科技风）
 *   marker       - 荧光笔（中性灰 + 黄绿荧光笔，浅色代码块）
 *
 * 内置主题 ID（wenyan-mcp 自带）:
 *   default, solarized-light, dracula, github, monokai,
 *   nord, one-dark, tokyo-night
 */

import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

// ── 微信凭据（从环境变量读取；运行前先 export WECHAT_APP_ID / WECHAT_APP_SECRET） ──
if (!process.env.WECHAT_APP_ID || !process.env.WECHAT_APP_SECRET) {
  throw new Error('请先设置环境变量 WECHAT_APP_ID 和 WECHAT_APP_SECRET');
}

// ── 摘要（可选）：环境变量 WECHAT_DIGEST 写进草稿的摘要栏 ─────────
// wenyan 的 publishToDraft 不收摘要：在它发「新建草稿」请求时补上。要在导入 wenyan 之前包好 fetch（它载入时就取走了 fetch）。
// 不设就不动，微信默认截取正文前 54 字；摘要上限 120 字由调用方检查
if (process.env.WECHAT_DIGEST) {
  const digest = process.env.WECHAT_DIGEST;
  const rawFetch = globalThis.fetch;
  globalThis.fetch = (url, init) => {
    if (String(url).includes('/cgi-bin/draft/add') && init && typeof init.body === 'string') {
      const body = JSON.parse(init.body);
      for (const a of body.articles || []) a.digest = digest;
      init = { ...init, body: JSON.stringify(body) };
    }
    return rawFetch(url, init);
  };
}

// ── wenyan-mcp 核心库路径 ──────────────────────────────
const corePath = '/opt/homebrew/lib/node_modules/@wenyan-md/mcp/node_modules/@wenyan-md/core/dist';
const { registerTheme, getAllGzhThemes } = await import(`${corePath}/core.js`);
const { getGzhContent } = await import(`${corePath}/wrapper.js`);
const { publishToDraft } = await import(`${corePath}/publish.js`);

// ── 自定义主题 CSS 路径 ────────────────────────────────
const __dirname = dirname(fileURLToPath(import.meta.url));
const themesDir = resolve(__dirname, '..', 'assets', 'themes');

// 自定义主题定义
const customThemes = [
  {
    meta: {
      id: 'sunset-glow',
      name: 'Sunset Glow',
      description: '温暖的落日渐变色调，橙红色系，优雅大气',
      appName: '落日晚霞',
      author: 'AI Designer'
    },
    cssFile: 'sunset-glow.css'
  },
  {
    meta: {
      id: 'ink-bamboo',
      name: 'Ink Bamboo',
      description: '中国风水墨竹叶色调，古朴雅致',
      appName: '墨竹清韵',
      author: 'AI Designer'
    },
    cssFile: 'ink-bamboo.css'
  },
  {
    meta: {
      id: 'starry-geek',
      name: 'Starry Geek',
      description: '深色科技风格，紫蓝渐变，现代酷炫',
      appName: '星空极客',
      author: 'AI Designer'
    },
    cssFile: 'starry-geek.css'
  },
  {
    meta: {
      id: 'marker',
      name: 'Marker',
      description: '中性灰正文 + 黄绿荧光笔加粗，小一号字、宽字距、两倍行距，不铺底色',
      appName: '荧光笔',
      author: 'AI Designer'
    },
    cssFile: 'marker.css'
  }
];

// ── 注册所有自定义主题 ─────────────────────────────────
for (const theme of customThemes) {
  const cssPath = resolve(themesDir, theme.cssFile);
  const css = readFileSync(cssPath, 'utf-8');
  registerTheme({
    meta: theme.meta,
    getCss: () => Promise.resolve(css)
  });
  console.log(`✓ 已注册主题: ${theme.meta.appName} (${theme.meta.id})`);
}

// 显示所有可用主题
const allThemes = getAllGzhThemes();
console.log(`\n可用主题总数: ${allThemes.length}`);
console.log('主题列表:', allThemes.map(t => t.meta.id).join(', '));

// ── 解析命令行参数 ─────────────────────────────────────
const args = process.argv.slice(2);
if (args.length < 2) {
  console.error('\n用法: node publish.mjs <md_file> <theme_ids>');
  console.error('示例: node publish.mjs ./article.md sunset-glow,ink-bamboo');
  process.exit(1);
}

const mdPath = resolve(args[0]);
const themeIds = args[1].split(',').map(s => s.trim());

// 读取 Markdown 文件
const mdContent = readFileSync(mdPath, 'utf-8');
console.log(`\n📄 文件: ${mdPath}`);
console.log(`🎨 主题: ${themeIds.join(', ')}`);

// 正文第一个元素去掉段前距。wenyan 不套用带冒号的选择器（:first-child 写进主题不生效），只能渲染后改行内样式
function zeroFirstMarginTop(html) {
  const open = html.match(/<section[^>]*\bid="wenyan"[^>]*>/);
  if (!open) return html;
  const start = open.index + open[0].length;
  const tag = html.slice(start).match(/^\s*<([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>/);
  if (!tag) return html;
  const oldTag = tag[0];
  const newTag = /\sstyle="/.test(oldTag)
    ? oldTag.replace(/\sstyle="([^"]*)"/, (_, s) => ` style="${s.replace(/;?\s*$/, '')}; margin-top: 0px;"`)
    : oldTag.replace(/>$/, ' style="margin-top: 0px;">');
  return html.slice(0, start) + html.slice(start).replace(oldTag, newTag);
}

// 正文两端对齐（默认开，环境变量 WECHAT_JUSTIFY=0 关掉）。中文正文原则上两端对齐（W3C《中文排版需求》6.2）。
// 段落和列表项改成两端对齐；带不能断行的长串（网址、路径、长代码）的保持左对齐：两端对齐会把长串前面那一行的字距拉得很开。
// 主题自带的 left 也改成两端对齐；居中、右对齐这些主题特意写的不动。标题、代码块、表格单元格不碰。
// wenyan 不套用带冒号的选择器，也写不出「含链接的段落」，所以渲染后改行内样式
function justifyText(html) {
  // 只看显示出来的文字：链接文字是中文标题时照样两端对齐
  const hasLongToken = (inner) => {
    const text = inner.replace(/<[^>]+>/g, '');
    return /https?:\/\/|www\./i.test(text) || /[\x21-\x7E]{20,}/.test(text);
  };
  const keep = (openTag) => /text-align:\s*(?!left\b)[a-z]/.test(openTag);
  const setAlign = (openTag, align) => {
    if (/text-align:/.test(openTag)) return openTag.replace(/text-align:\s*[a-z-]+/, `text-align: ${align}`);
    return /\sstyle="/.test(openTag)
      ? openTag.replace(/\sstyle="([^"]*)"/, (_, s) => ` style="${s.replace(/;?\s*$/, '')}; text-align: ${align};"`)
      : openTag.replace(/>$/, ` style="text-align: ${align};">`);
  };
  return html
    .replace(/(<p\b[^>]*>)([\s\S]*?)(<\/p>)/g, (all, open, inner, close) => {
      if (keep(open) || /^\s*<img\b[^>]*>\s*$/.test(inner)) return all;
      return setAlign(open, hasLongToken(inner) ? 'left' : 'justify') + inner + close;
    })
    // 每个列表项只看自己的文字（到下一个 li 或子列表为止），嵌套的子项也各自处理
    .replace(/(<li\b[^>]*>)((?:(?!<\/?li\b|<[uo]l\b)[\s\S])*)/g, (all, open, inner) => {
      if (keep(open)) return all;
      return setAlign(open, hasLongToken(inner) ? 'left' : 'justify') + inner;
    });
}

// 图注排成居中灰色小字：图片下面紧贴着写的斜体（和图片在同一段），或者单独一段、以 ▲ 开头的斜体（*▲ 图注*）。
// 其他整段斜体、正文里的斜体都是普通斜体。只给 CAPTION_THEMES 里的主题用（sunset-glow、marker）：它们的主题文件里 em 只写了 italic
const CAPTION_THEMES = new Set(['sunset-glow', 'marker']);
const CAPTION_STYLE = 'color: #999; font-style: italic; display: block; text-align: center; font-size: 0.85em; margin: 4px 0 16px;';
function captionEm(html) {
  return html.replace(/(<p\b[^>]*>)((?:<img\b[^>]*>|<br\s*\/?>|\s)*?)<em\b[^>]*>((?:(?!<\/?(?:p|em)\b)[\s\S])*)<\/em>\s*(<\/p>)/g,
    (all, open, pre, inner, close) => {
      const afterImage = /<img\b/.test(pre);
      if (!afterImage && !inner.replace(/<[^>]+>/g, '').trim().startsWith('▲')) return all;
      return `${open}${pre}<em style="${CAPTION_STYLE}">${inner}</em>${close}`;
    });
}

// 几张图连着写（中间不空行，wenyan 会放进同一个段落）→ 横滑图集：每张占 80% 宽、露出下一张的边，手指左右滑。
// 后面紧贴着的一行斜体当图集的图注，放在图集下面。单独一段的一张图不动。2026-11-11 推草稿手机实测可用
function imageGalleries(html) {
  return html.replace(/(<p\b[^>]*>)\s*((?:<img\b[^>]*>\s*(?:<br\s*\/?>\s*)?){2,})(<em\b[^>]*>(?:(?!<\/?(?:p|em)\b)[\s\S])*<\/em>)?\s*<\/p>/g,
    (all, open, imgsHtml, caption) => {
      const imgs = imgsHtml.match(/<img\b[^>]*>/g);
      const items = imgs.map((img, i) => {
        const tag = img.replace(/\sstyle="[^"]*"/, '').replace(/\s*\/?>$/, ' style="display: block; width: 100%; height: auto; border-radius: 8px;">');
        return `<section style="display: inline-block; width: 80%; ${i < imgs.length - 1 ? 'margin-right: 3%; ' : ''}vertical-align: top; white-space: normal;">${tag}</section>`;
      }).join('');
      const gallery = `<section style="overflow-x: auto; overflow-y: hidden; white-space: nowrap; font-size: 0; line-height: 0; -webkit-overflow-scrolling: touch; margin: ${caption ? '22px 0 0' : '22px 0'};">${items}</section>`;
      return caption ? `${gallery}\n<p style="margin: 0 0 22px;">${caption}</p>` : gallery;
    });
}

// 表格一律套横向滚动容器：列多的表格左右滑，不被挤窄也不被截断（主题里表格不折行、按内容撑宽）。2026-11-11 手机实测可用
function wrapTables(html) {
  return html.replace(/<table\b[\s\S]*?<\/table>/g, (t) =>
    `<section style="overflow-x: auto; overflow-y: hidden; -webkit-overflow-scrolling: touch;">${t}</section>`);
}

// ── 逐个主题渲染并发布 ─────────────────────────────────
const results = [];

for (const themeId of themeIds) {
  const themeMeta = allThemes.find(t => t.meta.id === themeId);
  const themeName = themeMeta?.meta.appName || themeId;

  try {
    console.log(`\n━━━ ${themeName} (${themeId}) ━━━`);

    console.log('渲染中...');
    // 荧光笔配浅色代码块、不加 Mac 风格三个点；其他主题照旧
    const codeTheme = themeId === 'marker' ? 'atom-one-light' : 'atom-one-dark';
    const macStyle = themeId !== 'marker';
    // 最后一个参数是自动脚注：开着会给每个链接加 [n]，并在文末另起一段「引用链接」，和文章自己写的引用重复，所以关掉
    const gzhContent = await getGzhContent(mdContent, themeId, codeTheme, macStyle, false);
    gzhContent.content = zeroFirstMarginTop(gzhContent.content);
    if (CAPTION_THEMES.has(themeId)) gzhContent.content = captionEm(gzhContent.content);
    gzhContent.content = imageGalleries(gzhContent.content);
    gzhContent.content = wrapTables(gzhContent.content);
    if (process.env.WECHAT_JUSTIFY !== '0') gzhContent.content = justifyText(gzhContent.content);
    const title = gzhContent.title ?? '未命名文章';

    console.log(`标题: ${title}`);
    console.log('发布到草稿箱...');

    // publishToDraft 只收 4 个参数，凭据放第 4 个
    const response = await publishToDraft(
      title,
      gzhContent.content,
      gzhContent.cover ?? '',
      { appId: process.env.WECHAT_APP_ID, appSecret: process.env.WECHAT_APP_SECRET }
    );

    console.log(`✓ 成功! media_id: ${response.media_id}`);
    results.push({ themeId, themeName, success: true, mediaId: response.media_id });
  } catch (e) {
    console.log(`✗ 失败: ${e.message}`);
    results.push({ themeId, themeName, success: false, error: e.message });
  }
}

// ── 汇总 ───────────────────────────────────────────────
console.log('\n═══════════════════════════════════');
console.log('发布结果汇总:');
for (const r of results) {
  const status = r.success ? '✓' : '✗';
  const detail = r.success ? `media_id: ${r.mediaId}` : `错误: ${r.error}`;
  console.log(`  ${status} ${r.themeName} (${r.themeId}) - ${detail}`);
}
console.log('═══════════════════════════════════');

const successCount = results.filter(r => r.success).length;
console.log(`\n🎉 完成! ${successCount}/${results.length} 个主题发布成功`);
