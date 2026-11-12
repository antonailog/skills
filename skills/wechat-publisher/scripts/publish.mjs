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
 *   marker-lite  - 细荧光（默认模板：细淡荧光加粗，15px，浅色代码块）
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
  },
  {
    meta: {
      id: 'marker-lite',
      name: 'Marker Lite',
      description: '默认模板：浅灰正文 + 细淡黄绿荧光加粗，15px、行距 1.85，白底',
      appName: '细荧光',
      author: 'AI Designer'
    },
    cssFile: 'marker-lite.css'
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
// 其他整段斜体、正文里的斜体都是普通斜体。只给 CAPTION_THEMES 里的主题用（sunset-glow、marker、marker-lite）：它们的主题文件里 em 只写了 italic
// 图注一行放不下时分成两行、在合适的位置换：在中间附近找断点（优先标点后面，其次中文字之间、中英文交界、空格），
// 把图注切成前后两段、各自 inline-block。一行放得下时两段挨着排成一行；放不下时后一段整体换到下一行，
// 不会剩一个字单独一行，也不管手机多宽。只处理纯文字图注（带链接等标签的不动）。2026-11-11 用户要求
function balanceCaption(text) {
  if (text.includes('<')) return text;
  const units = text.match(/&[#a-zA-Z0-9]+;|[\s\S]/g) || [];
  const space = (u) => u === ' ' || u === '\t';
  const cjk = (u) => /[⺀-鿿豈-﫿＀-￯　-〿]/.test(u);
  const weight = units.map(u => cjk(u) ? 1 : space(u) ? 0.3 : 0.55);
  const total = weight.reduce((a, b) => a + b, 0);
  if (total <= 14) return text;
  const punct = /^[，、：；。！？,;:）)」』”’—]$/;
  // 行首不能出现的（后半段不能以它开头）、行尾不能出现的（前半段不能以它结尾）；不换行空格前后都不断
  const noStart = /^[，、：；。！？,;:）)」』”’—》〉】\]…!?.%·]$|^&nbsp;$|^\u00a0$/;
  const noEnd = /^[「『“‘（(《〈【\[]$|^&nbsp;$|^\u00a0$/;
  const pick = (ok, lo, hi) => {
    let best = -1, bestDiff = Infinity, left = 0;
    for (let k = 0; k < units.length - 1; k++) {
      left += weight[k];
      if (left < 4 || left < total * lo || left > total * hi || !ok(units[k], units[k + 1])) continue;
      if (noStart.test(units[k + 1]) || noEnd.test(units[k])) continue;
      const d = Math.abs(left - total / 2);
      if (d < bestDiff) { bestDiff = d; best = k; }
    }
    return best;
  };
  let k = pick((a) => punct.test(a) || space(a), 0.25, 0.75);
  if (k < 0) k = pick((a, b) => (cjk(a) && cjk(b)) || (cjk(a) !== cjk(b) && !space(a) && !space(b)), 0.3, 0.7);
  if (k < 0) return text;
  // 断点在空格上时，空格放在两段之间：排在同一行时照常显示，换行时落在行尾
  // 只把半角空格挪到两段之间；全角空格是正文的一部分，原样留着
  const L = units.slice(0, k + 1).join(''), R = units.slice(k + 1).join('');
  const gap = /[ \t]$/.test(L) || /^[ \t]/.test(R) ? ' ' : '';
  return `<span style="display: inline-block;">${L.replace(/[ \t]+$/, '')}</span>${gap}<span style="display: inline-block;">${R.replace(/^[ \t]+/, '')}</span>`;
}

const CAPTION_THEMES = new Set(['sunset-glow', 'marker', 'marker-lite']);
const CAPTION_STYLE = 'color: #999; font-style: italic; display: block; text-align: center; font-size: 0.85em; margin: 4px 0 16px;';
function captionEm(html) {
  return html.replace(/(<p\b[^>]*>)((?:<img\b[^>]*>|<br\s*\/?>|\s)*?)<em\b[^>]*>((?:(?!<\/?(?:p|em)\b)[\s\S])*)<\/em>\s*(<\/p>)/g,
    (all, open, pre, inner, close) => {
      const afterImage = /<img\b/.test(pre);
      if (!afterImage && !inner.replace(/<[^>]+>/g, '').trim().startsWith('▲')) return all;
      return `${open}${pre}<em style="${CAPTION_STYLE}">${balanceCaption(inner)}</em>${close}`;
    });
}

// 读本机图片的宽高（PNG、JPEG、GIF、WebP 只看文件头），读不出返回 null。用来定自动滑动图集的框比例
function imageSize(src) {
  try {
    let p = String(src || '');
    if (/^https?:/i.test(p)) return null;
    p = decodeURIComponent(p.replace(/^file:\/\//, ''));
    const b = readFileSync(p);
    if (b[0] === 0x89 && b.toString('ascii', 1, 4) === 'PNG') return [b.readUInt32BE(16), b.readUInt32BE(20)];
    if (b.toString('ascii', 0, 3) === 'GIF') return [b.readUInt16LE(6), b.readUInt16LE(8)];
    if (b.toString('ascii', 0, 4) === 'RIFF' && b.toString('ascii', 8, 12) === 'WEBP') {
      const kind = b.toString('ascii', 12, 16);
      if (kind === 'VP8X') return [1 + b.readUIntLE(24, 3), 1 + b.readUIntLE(27, 3)];
      if (kind === 'VP8 ') return [b.readUInt16LE(26) & 0x3fff, b.readUInt16LE(28) & 0x3fff];
      if (kind === 'VP8L') { const v = b.readUInt32LE(21); return [(v & 0x3fff) + 1, ((v >> 14) & 0x3fff) + 1]; }
    }
    if (b[0] === 0xff && b[1] === 0xd8) {
      // 手机竖拍的照片像素横着存、方向记在 EXIF Orientation：5-8 要转 90 度，宽高对调
      let i = 2, rotate = false;
      while (i + 9 < b.length) {
        if (b[i] !== 0xff) { i++; continue; }
        const m = b[i + 1];
        if (m === 0xe1 && b.toString('ascii', i + 4, i + 8) === 'Exif') {
          const t = i + 10, le = b.toString('ascii', t, t + 2) === 'II';
          const u16 = (o) => le ? b.readUInt16LE(o) : b.readUInt16BE(o);
          const u32 = (o) => le ? b.readUInt32LE(o) : b.readUInt32BE(o);
          const ifd = t + u32(t + 4), count = u16(ifd);
          for (let e = 0; e < count; e++) {
            const at = ifd + 2 + e * 12;
            if (u16(at) === 0x0112) { rotate = u16(at + 8) >= 5 && u16(at + 8) <= 8; break; }
          }
        }
        if (m >= 0xc0 && m <= 0xcf && m !== 0xc4 && m !== 0xc8 && m !== 0xcc) {
          const w = b.readUInt16BE(i + 7), h = b.readUInt16BE(i + 5);
          return rotate ? [h, w] : [w, h];
        }
        i += 2 + b.readUInt16BE(i + 2);
      }
    }
  } catch {}
  return null;
}

// 几张图连着写（中间不空行，wenyan 会放进同一个段落）→ 自动滑动图集：同一个位置每张停 2.6 秒、0.5 秒滑到下一张，循环；
// 用 SVG 自带的动画（不用脚本，公众号会删脚本），图片嵌在 foreignObject 里，文颜照常传图。
// 末尾接一张第一张的复制，循环回到开头时看不出跳。框的比例取这组图高宽比的中间值（读不出尺寸的图按 4:3 算，
// 比如网络图片；结果限制在 2.5:1 到 2:3 之间），比例不同的图等比缩放放进框里（不裁切）。
// 后面紧贴着的一行斜体当图集的图注，放在图集下面。单独一段的一张图不动。
// 2026-11-11 推草稿手机实测过 SVG 位移动画和 foreignObject 里的图都能显示；用户定多张图要自动滑动，不要圆点
const CAROUSEL_HOLD = 2.6;
const CAROUSEL_MOVE = 0.5;
function imageGalleries(html) {
  return html.replace(/(<p\b[^>]*>)\s*((?:<img\b[^>]*>\s*(?:<br\s*\/?>\s*)?){2,})(<em\b[^>]*>(?:(?!<\/?(?:p|em)\b)[\s\S])*<\/em>)?\s*<\/p>/g,
    (all, open, imgsHtml, caption) => {
      const imgs = imgsHtml.match(/<img\b[^>]*>/g);
      const n = imgs.length;
      const ratios = imgs.map(img => {
        const size = imageSize((img.match(/\ssrc="([^"]+)"/) || [])[1]);
        return size && size[0] > 0 && size[1] > 0 ? size[1] / size[0] : 0.75;
      }).sort((a, b) => a - b);
      const mid = ratios.length / 2;
      const median = ratios.length % 2 ? ratios[Math.floor(mid)] : (ratios[mid - 1] + ratios[mid]) / 2;
      const ratio = Math.min(1.5, Math.max(0.4, median));
      const W = 1000, H = Math.round(W * ratio), T = CAROUSEL_HOLD + CAROUSEL_MOVE, D = n * T;
      const f = (x) => Number(x.toFixed(4));
      const values = [], keyTimes = [];
      for (let i = 0; i < n; i++) { values.push(`${-i * W} 0`, `${-i * W} 0`); keyTimes.push(f(i * T / D), f((i * T + CAROUSEL_HOLD) / D)); }
      values.push(`${-n * W} 0`); keyTimes.push(1);
      const frames = [...imgs, imgs[0]].map(img => img
        .replace(/\sstyle="[^"]*"/, '').replace(/\s(?:width|height)="[^"]*"/g, '')
        .replace(/\s*\/?>$/, ` style="display: inline-block; width: ${W}px; height: ${H}px; object-fit: contain; vertical-align: top;">`)).join('');
      const svg = `<svg viewBox="0 0 ${W} ${H}" width="100%" style="display: block; width: 100%;" xmlns="http://www.w3.org/2000/svg">`
        + `<g><animateTransform attributeName="transform" type="translate" values="${values.join(';')}" keyTimes="${keyTimes.join(';')}" dur="${f(D)}s" repeatCount="indefinite"/>`
        + `<foreignObject x="0" y="0" width="${W * (n + 1)}" height="${H}"><section style="width: ${W * (n + 1)}px; height: ${H}px; white-space: nowrap; font-size: 0; line-height: 0; background: #f4f4f4;">${frames}</section></foreignObject></g>`
        + '</svg>';
      const gallery = `<section style="margin: ${caption ? '22px 0 0' : '22px 0'}; line-height: 0; overflow: hidden; border-radius: 8px;">${svg}</section>`;
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
    // 荧光笔、细荧光配浅色代码块、不加 Mac 风格三个点；其他主题照旧
    const lightCode = themeId === 'marker' || themeId === 'marker-lite';
    const codeTheme = lightCode ? 'atom-one-light' : 'atom-one-dark';
    const macStyle = !lightCode;
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
