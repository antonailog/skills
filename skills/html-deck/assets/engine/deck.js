/* html-deck 播放引擎：缩放、翻页、分步、页签、嵌入、备注、翻页笔、演讲者视图、总览、动效、图表、二维码。
   页面结构：<div id="stage"> 里每页一个 <section class="slide">，</div><!-- /stage --> 结束。按键见 references/presenting.md */
(function () {
  'use strict';
  const q = new URLSearchParams(location.search);
  const MODE = q.has('presenter') ? 'presenter' : q.has('mirror') ? 'mirror' : 'main';
  const root = document.documentElement;
  const stage = document.getElementById('stage');
  if (!stage) return;
  const slides = [...stage.querySelectorAll(':scope > section.slide')];
  const reduce = matchMedia('(prefers-reduced-motion: reduce)');
  const pad = (n) => String(n).padStart(2, '0');
  const el = (tag, attrs, html) => { const e = document.createElement(tag); for (const k in attrs || {}) e.setAttribute(k, attrs[k]); if (html != null) e.innerHTML = html; return e; };
  let cur = 0, t0 = null, presenterWin = null;
  const PUBLIC = root.hasAttribute('data-public');   // 网站版（scripts/website.py 加上）：没有备注、不开演讲者视图
  const hooks = [];

  // 换风格：?theme=keynote 临时换（渲染风格对比用）
  if (q.get('theme')) { const l = document.querySelector('link[data-theme-link]'); if (l) l.href = l.getAttribute('href').replace(/themes\/[^/]+\.css/, `themes/${q.get('theme')}.css`); }
  if (MODE !== 'main') root.classList.add(MODE);
  if (!root.dataset.transition) root.dataset.transition = (getComputedStyle(root).getPropertyValue('--transition') || 'fade').trim() || 'fade';

  // ───── 图表：<figure class="chart" data-type="bar|hbar|line|donut" data-labels="a,b" data-values="1,2[;3,4]"> ─────
  const NS = 'http://www.w3.org/2000/svg';
  const sv = (tag, attrs, text) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (text != null) e.textContent = text; return e; };
  const fmt = (v, unit) => (Math.round(v * 100) / 100).toLocaleString('en-US') + (unit || '');
  function renderChart(fig) {
    fig.querySelectorAll('svg[data-gen]').forEach((s) => s.remove());
    const type = fig.dataset.type || 'bar', unit = fig.dataset.unit || '';
    const labels = (fig.dataset.labels || '').split(',').map((s) => s.trim());
    const series = (fig.dataset.values || '').split(';').map((r) => r.split(',').map((x) => { const v = parseFloat(x); return Number.isFinite(v) ? v : 0; }));
    const names = (fig.dataset.series || '').split(',').map((s) => s.trim()).filter(Boolean);
    const hl = (fig.dataset.hl || '').split(',').filter(Boolean).map(Number);
    const cap = fig.querySelector('figcaption'), cw = fig.clientWidth, ch = fig.clientHeight - (cap ? cap.offsetHeight + 6 : 0);
    const W = Math.round(cw) || 1000, H = +(fig.dataset.h || 0) || (ch > 80 ? Math.round(ch) : Math.round(W * .5));
    fig._w = cw;
    const svg = sv('svg', { viewBox: `0 0 ${W} ${H}`, 'data-gen': '', preserveAspectRatio: 'xMidYMid meet', role: 'img' });
    const color = (i) => `var(--c${(i % 5) + 1})`;
    const all = series.flat(), raw = +(fig.dataset.max || 0) || Math.max(...all, 0) * 1.08 || 1;
    const step = (() => { const r = raw / 4, p = Math.pow(10, Math.floor(Math.log10(r))); return [1, 2, 2.5, 5, 10].map((m) => m * p).find((x) => x >= r); })();
    const max = fig.dataset.max ? raw : step * 4;
    if (type === 'donut') {
      const v = series[0], sum = v.reduce((a, b) => a + b, 0) || 1, r = Math.min(H * .36, W * .2), C = 2 * Math.PI * r, cx = r + 40, cy = H / 2, lx = cx + r + 70;
      let off = 0;
      v.forEach((x, i) => {
        const L = (x / sum) * C;
        svg.append(sv('circle', { class: 'arc', cx, cy, r, stroke: color(i), 'stroke-width': r * .42, transform: `rotate(-90 ${cx} ${cy})`, 'stroke-dashoffset': -off, style: `--L:${L}px;--C:${C}px` }));
        const y = cy - (v.length - 1) * 23 + i * 46 + 7;
        svg.append(sv('rect', { x: lx, y: y - 17, width: 18, height: 18, fill: color(i) }));
        svg.append(sv('text', { x: lx + 28, y, class: 'lbl', 'font-size': 20 }, labels[i] || ''));
        svg.append(sv('text', { x: W - 10, y, class: 'val', 'text-anchor': 'end' }, fmt(Math.round((x / sum) * 100), '%')));
        off += L;
      });
    } else if (type === 'hbar') {
      const v = series[0], n = Math.max(v.length, 1), top = 10, rowH = (H - top - 10) / n, x0 = Math.min(220, W * .28), pw = W - x0 - 110;
      v.forEach((x, i) => {
        const bh = Math.min(rowH * .58, 46), y = top + i * rowH + (rowH - bh) / 2, w = (x / max) * pw;
        svg.append(sv('text', { x: x0 - 14, y: y + bh / 2 + 7, class: 'lbl', 'text-anchor': 'end', 'font-size': 18 }, labels[i] || ''));
        svg.append(sv('rect', { class: 'hbar', x: x0, y, width: Math.max(w, 1), height: bh, fill: !hl.length || hl.includes(i) ? 'var(--c1)' : 'var(--c2)' }));
        svg.append(sv('text', { x: x0 + w + 10, y: y + bh / 2 + 7, class: 'val' }, fmt(x, unit)));
      });
    } else {
      const left = 70, right = 30, top = 30, bottom = 54, pw = W - left - right, ph = H - top - bottom, n = Math.max(labels.length, ...series.map((v) => v.length), 1);
      for (let g = 0; g <= 4; g++) { const y = top + ph - (g / 4) * ph; svg.append(sv('line', { class: g ? 'grid' : 'axis', x1: left, x2: W - right, y1: y, y2: y })); if (g) svg.append(sv('text', { x: left - 12, y: y + 6, class: 'lbl', 'text-anchor': 'end' }, fmt((max * g) / 4))); }
      labels.forEach((lb, i) => svg.append(sv('text', { x: left + (pw / n) * (i + .5), y: H - 18, class: 'lbl', 'text-anchor': 'middle', 'font-size': 18 }, lb)));
      if (type === 'line') {
        series.forEach((v, s) => {
          const pts = v.map((x, i) => [left + (pw / n) * (i + .5), top + ph - (x / max) * ph]);
          let L = 0; for (let i = 1; i < pts.length; i++) L += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
          svg.append(sv('path', { class: 'ln', d: 'M' + pts.map((p) => p.join(' ')).join('L'), stroke: color(s), style: `--L:${Math.ceil(L) + 2}px` }));
          pts.forEach((p, i) => { svg.append(sv('circle', { class: 'dot', cx: p[0], cy: p[1], r: 7, fill: color(s) })); if (i === pts.length - 1 || hl.includes(i)) svg.append(sv('text', { x: p[0], y: p[1] - 16, class: 'val', 'text-anchor': 'middle' }, fmt(v[i], unit))); });
          if (names[s]) svg.append(sv('text', { x: pts[pts.length - 1][0] + 12, y: pts[pts.length - 1][1] + 6, class: 'lbl', fill: color(s) }, names[s]));
        });
      } else {
        const m = series.length, gw = pw / n, bw = (gw * .58) / m;
        if (m > 1) names.forEach((nm, s) => { const lx = W - right - (names.length - s) * 150; svg.append(sv('rect', { x: lx, y: 4, width: 16, height: 16, fill: color(s) })); svg.append(sv('text', { x: lx + 24, y: 19, class: 'lbl', 'font-size': 16 }, nm)); });
        series.forEach((v, s) => v.forEach((x, i) => {
          const h = (x / max) * ph, bx = left + gw * i + gw * .21 + bw * s, by = top + ph - h;
          const fill = m > 1 ? color(s) : hl.length ? (hl.includes(i) ? 'var(--c1)' : 'var(--c2)') : 'var(--c1)';
          svg.append(sv('rect', { class: 'bar', x: bx, y: by, width: bw - 4, height: Math.max(h, 1), fill }));
          svg.append(sv('text', { x: bx + (bw - 4) / 2, y: by - 10, class: 'val', 'text-anchor': 'middle' }, fmt(x, unit)));
        }));
      }
    }
    fig.prepend(svg);
  }
  document.querySelectorAll('figure.chart').forEach(renderChart);

  // ───── 二维码：<div class="qr" data-qr="网址"> ─────
  if (window.qrcode) document.querySelectorAll('[data-qr]').forEach((e) => {
    const qr = window.qrcode(0, 'M'); qr.addData(e.dataset.qr); qr.make();
    e.querySelectorAll('[data-gen]').forEach((x) => x.remove());
    const box = document.createElement('div'); box.innerHTML = qr.createSvgTag({ cellSize: 4, margin: 0, scalable: true });
    const s = box.firstElementChild; s.setAttribute('data-gen', ''); s.style.width = '100%'; s.style.height = '100%'; e.append(s);
  });

  // ───── 数字滚动：.stat .v 和 [data-count] 里只有一个数字时，出现时从 0 滚到目标 ─────
  const NUM = /^([^\d-]*)(-?\d[\d,]*\.?\d*)([^\d]*)$/;
  const numNode = (e) => { const w = document.createTreeWalker(e, NodeFilter.SHOW_TEXT); let n; while ((n = w.nextNode())) if (/\d/.test(n.nodeValue)) return n; return null; };
  const counters = [...document.querySelectorAll('.stat .v, [data-count]')].filter((e) => NUM.test(e.textContent.trim()) && numNode(e));
  function countUp(e) {   // 只动装着数字的那段文字，里面的 <small>% 之类不动
    if (e._run) return;
    const tn = numNode(e), m = tn && tn.nodeValue.match(/^([^\d-]*)(-?\d[\d,]*\.?\d*)([\s\S]*)$/); if (!m) return;
    e._tn = tn; e._orig = tn.nodeValue; e._run = true;
    const target = parseFloat(m[2].replace(/,/g, '')), dec = (m[2].split('.')[1] || '').length, comma = m[2].includes(','), t1 = performance.now();
    const tick = (now) => {
      if (!e._run) return;
      const p = Math.min(1, (now - t1) / 900), v = target * (1 - Math.pow(1 - p, 3));
      let s = v.toFixed(dec); if (comma) s = Number(s).toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec });
      tn.nodeValue = m[1] + s + m[3];
      if (p < 1) requestAnimationFrame(tick); else { tn.nodeValue = e._orig; e._run = false; e._done = true; }
    };
    requestAnimationFrame(tick);
  }
  function settle() { counters.forEach((e) => { if (e._run) { e._run = false; e._tn.nodeValue = e._orig; } }); }

  // ───── 分步：data-steps="选择器 | 选择器"，或元素上写 data-step="2" ─────
  slides.forEach((s) => {
    (s.dataset.steps || '').split('|').forEach((sel, n) => {
      if (!sel.trim()) return;
      try { s.querySelectorAll(sel.split(',').map((x) => ':scope ' + x.trim()).join(',')).forEach((e) => { e.classList.add('fr'); e.setAttribute('data-fr', n + 1); }); }
      catch (err) { console.error(`第 ${slides.indexOf(s) + 1} 页 data-steps 里的选择器写错了：${sel.trim()}`); }
    });
    s.querySelectorAll('[data-step]').forEach((e) => { e.classList.add('fr'); e.setAttribute('data-fr', e.dataset.step); });
    s._n = Math.max(0, ...[...s.querySelectorAll('.fr')].map((e) => +e.getAttribute('data-fr') || 0));
    s._k = 0;
    s._tabs = [...s.querySelectorAll('.tabs button')];
  });
  const tabAt = (s) => Math.max(0, s._tabs.findIndex((b) => b.classList.contains('cur')));
  const visible = (e, s) => { const f = e.closest('.fr'); if (f && !f.classList.contains('in')) return false; const p = e.closest('.pane'); return !p || p.classList.contains('cur'); };

  function setTab(s, i) {
    s._tabs.forEach((b, j) => b.classList.toggle('cur', j === i));
    s.querySelectorAll('.pane').forEach((p, j) => p.classList.toggle('cur', j === i));
    loadFrames(s); paint(s);
  }
  // 把这一页出现到第 _k 步；页码前画进度点（●已出现 ○还没出现，页签也算）；出现了的图表和数字开始动
  function paint(s) {
    s.querySelectorAll('.fr').forEach((e) => { const n = +e.getAttribute('data-fr') || 0; e.classList.toggle('in', n <= s._k); e.classList.toggle('now', n === s._k); });
    const on = s.classList.contains('on');
    s.querySelectorAll('figure.chart').forEach((c) => {
      const v = on && visible(c, s);
      if (v && c._w !== c.clientWidth) { const was = c.classList.contains('play'); renderChart(c); if (was) c.classList.add('play'); }
      if (v && !c.classList.contains('play')) { if (reduce.matches) c.classList.add('play'); else requestAnimationFrame(() => requestAnimationFrame(() => c.classList.add('play'))); }
      if (!v) c.classList.remove('play');
    });
    counters.forEach((e) => { if (!s.contains(e)) return; const v = on && visible(e, s); if (v && !e._done && !reduce.matches) countUp(e); if (!v) { if (e._run) { e._run = false; e._tn.nodeValue = e._orig; } e._done = false; } });
    const p = s.querySelector('.pg');
    if (p) {
      const total = s._n + Math.max(0, s._tabs.length - 1), done = s._k + (s._tabs.length ? tabAt(s) : 0);
      p.innerHTML = (total ? `<i>${'●'.repeat(done)}${'○'.repeat(total - done)}</i>` : '') + `${pad(slides.indexOf(s) + 1)} / ${pad(slides.length)}`;
    }
  }
  function loadFrames(s) {
    s.querySelectorAll('iframe[data-src]').forEach((f) => { const p = f.closest('.pane'); if (!f.src && !f.closest('.box.off') && (!p || p.classList.contains('cur'))) f.src = f.dataset.src; });
  }
  function show(i, push = true, atEnd = false) {   // atEnd：从后一页退回来时，这一页直接是全部出现的样子
    if (i < 0 || i > slides.length - 1) return;
    const prev = cur, changed = i !== cur;
    if (changed) slides[prev].classList.remove('on');
    cur = i;
    const s = slides[cur];
    slides.forEach((x, j) => x.classList.toggle('on', j === cur));
    if (changed && !reduce.matches && root.dataset.transition !== 'none' && MODE !== 'presenter') {
      s.classList.remove('enter', 'back'); void s.offsetWidth; s.classList.add('enter'); if (i < prev) s.classList.add('back');
      s.addEventListener('animationend', () => s.classList.remove('enter', 'back'), { once: true });
    }
    if (changed) paint(slides[prev]);
    s._k = atEnd ? s._n : 0;
    if (s._tabs.length) setTab(s, atEnd ? s._tabs.length - 1 : 0); else paint(s);
    loadFrames(s);
    document.querySelectorAll('video').forEach((v) => { if (s.contains(v) && MODE === 'main') v.play().catch(() => {}); else v.pause(); });
    if (push && MODE === 'main') history.replaceState(null, '', '#' + (cur + 1));
    const n = s.querySelector('.note');
    const npg = document.getElementById('n-pg'), nb = document.getElementById('n-body');
    if (npg) npg.textContent = `${cur + 1} / ${slides.length}`;
    if (nb) nb.innerHTML = n ? n.innerHTML : '';
    if (cur > 0 && t0 === null) t0 = Date.now();
    if (document.activeElement && document.activeElement.tagName === 'IFRAME') document.activeElement.blur();
    hooks.forEach((h) => h(cur));
  }
  // 往前或往后一步：先走本页的步骤，再走页签，都走完才翻页
  function step(dir) {
    const s = slides[cur];
    if (document.body.classList.contains('ed-on')) { show(cur + dir, true, dir < 0); return emit(); }
    if (dir > 0) { if (s._k < s._n) { s._k++; paint(s); } else if (s._tabs.length && tabAt(s) < s._tabs.length - 1) setTab(s, tabAt(s) + 1); else show(cur + 1); }
    else { if (s._tabs.length && tabAt(s) > 0) setTab(s, tabAt(s) - 1); else if (s._k > 0) { s._k--; paint(s); } else show(cur - 1, true, true); }
    emit();
  }

  // ───── 缩放：页面顶上有网站顶栏时（<html data-top=".site-tb">），扣掉它的高度 ─────
  function fit() {
    const tb = root.dataset.top && document.querySelector(root.dataset.top);
    const h = tb && getComputedStyle(tb).display !== 'none' ? tb.offsetHeight : 0;
    root.style.setProperty('--deck-top', h + 'px');
    const k = Math.min(innerWidth / 1280, (innerHeight - h) / 720);
    stage.style.top = `calc(50% + ${h / 2}px)`;
    stage.style.transform = `translate(-50%, -50%) scale(${k})`;
  }

  // ───── 演讲者视图和同步：两个窗口互相 postMessage（本地文件打开也能用） ─────
  const state = () => ({ deck: 1, type: 'go', i: cur, k: slides[cur]._k, tab: tabAt(slides[cur]) });
  function apply(st) {
    if (st.i !== cur) show(st.i, true, false);
    const s = slides[cur]; s._k = Math.min(st.k || 0, s._n);
    if (s._tabs.length) setTab(s, Math.min(st.tab || 0, s._tabs.length - 1)); else paint(s);
    if (MODE === 'presenter') updatePresenter();
  }
  function toOther(msg) {
    if (MODE === 'main' && presenterWin && !presenterWin.closed) presenterWin.postMessage(msg, '*');
    if (MODE === 'presenter' && window.opener) window.opener.postMessage(msg, '*');
  }
  function emit() {
    toOther(state());
    if (MODE === 'presenter') updatePresenter();
  }
  addEventListener('message', (e) => {
    const d = e.data; if (!d || d.deck !== 1 || !e.source) return;
    // 只听演讲者视图这组窗口：主窗口认它打开的演讲者窗口（刷新后靠 opener 认回来），演讲者窗口认主窗口，预览认装它的演讲者窗口；嵌在页里的网页发来的不算
    let peer = false;
    try { peer = e.source === presenterWin || e.source === window.opener || (MODE === 'mirror' && e.source === window.parent) || (MODE === 'main' && e.source.opener === window); } catch (err) {}
    if (!peer) return;
    if (d.type === 'go') { apply(d); if (MODE === 'main' && e.source && e.source !== window) presenterWin = e.source; }
    if (d.type === 'blank') showBlank(d.v);   // 在演讲者窗口按 B / W，观众那边的主窗口跟着黑屏
    // 演讲者窗口刚打开时、主窗口刷新过后（它忘了演讲者窗口是谁），都靠 hello 重新接上
    if (d.type === 'hello' && MODE === 'main' && e.source && (d.first || !presenterWin || presenterWin.closed)) { presenterWin = e.source; presenterWin.postMessage(state(), '*'); presenterWin.postMessage({ deck: 1, type: 'blank', v: blank.className }, '*'); }
  });
  function openPresenter() {
    if (presenterWin && !presenterWin.closed) { presenterWin.close(); presenterWin = null; return; }   // 再按一次 P 关掉
    const url = location.href.split('#')[0].split('?')[0] + '?presenter#' + (cur + 1);
    presenterWin = window.open(url, 'deck-presenter', 'width=1280,height=800');
  }
  let pv = null;
  function buildPresenter() {
    const base = location.href.split('#')[0].split('?')[0];
    pv = el('div', { id: 'pv' }, `<div class="frm cur"><iframe title="当前页"></iframe></div>
      <div class="side"><h4>下一页</h4><div class="frm nx"><iframe title="下一页"></iframe><div class="pv-end" hidden>最后一页</div></div><h4>备注</h4><div class="nt"></div></div>
      <div class="bar"><span class="clock">00:00</span><span class="pg"></span><span class="now"></span><button type="button" data-a="prev">上一步</button><button type="button" data-a="next">下一步</button><button type="button" data-a="reset">计时归零</button><span style="color:#888;font-size:13px">→ / PageDown 下一步 · ← 上一步 · T 计时归零 · Esc 关闭演讲者视图</span></div>`);
    document.body.append(pv);
    const [fc, fn] = pv.querySelectorAll('iframe');
    fc.src = base + '?mirror#' + (cur + 1); fn.src = base + '?mirror#' + Math.min(cur + 2, slides.length);
    fc.addEventListener('load', updatePresenter); fn.addEventListener('load', updatePresenter);
    pv.addEventListener('click', (e) => { const a = e.target.dataset.a; if (a === 'prev') step(-1); if (a === 'next') step(1); if (a === 'reset') t0 = Date.now(); });
    t0 = Date.now();
    if (window.opener) { window.opener.postMessage({ deck: 1, type: 'hello', first: true }, '*'); setInterval(() => { if (window.opener && !window.opener.closed) window.opener.postMessage({ deck: 1, type: 'hello' }, '*'); }, 1000); }
  }
  function updatePresenter() {
    if (!pv) return;
    const [fc, fn] = pv.querySelectorAll('iframe');
    const s = slides[cur];
    try { fc.contentWindow.postMessage(state(), '*'); } catch (e) {}
    const last = cur >= slides.length - 1;
    pv.querySelector('.pv-end').hidden = !last; fn.style.visibility = last ? 'hidden' : '';
    if (!last) try { fn.contentWindow.postMessage({ deck: 1, type: 'go', i: cur + 1, k: 0, tab: 0 }, '*'); } catch (e) {}
    const n = s.querySelector('.note'); pv.querySelector('.nt').innerHTML = n ? n.innerHTML : '<span style="color:#777">这页没有备注</span>';
    const total = s._n + Math.max(0, s._tabs.length - 1), done = s._k + (s._tabs.length ? tabAt(s) : 0);
    pv.querySelector('.pg').textContent = `第 ${cur + 1} / ${slides.length} 页` + (total ? `　步骤 ${done} / ${total}` : '');
  }

  // ───── 总览：O 键，点哪页跳哪页 ─────
  let ov = null;
  function toggleOverview(force) {
    const open = force == null ? !(ov && ov.classList.contains('on')) : force;
    if (open && ov) { ov.remove(); ov = null; }   // 每次打开重建：编辑后的内容、滚到一半的数字都按最新的来
    if (!ov) {
      settle();
      ov = el('div', { id: 'ov' }); document.body.append(ov);
      slides.forEach((s, i) => {
        const t = el('div', { class: 'ovt', 'data-i': i }, `<b>${i + 1}</b>`);
        const c = s.cloneNode(true); c.classList.add('on'); c.classList.remove('enter', 'back'); c.removeAttribute('id');
        c.querySelectorAll('.note').forEach((x) => x.remove());
        c.querySelectorAll('iframe').forEach((f) => f.replaceWith(el('div', { style: 'position:absolute;inset:0;background:var(--soft)' })));
        c.querySelectorAll('video').forEach((v) => v.replaceWith(el('div', { style: 'position:absolute;inset:0;background:#111' })));
        c.querySelectorAll('.box').forEach((b) => b.classList.add('off'));
        c.querySelectorAll('figure.chart').forEach((f) => f.classList.add('play'));
        c.querySelectorAll('[id]').forEach((x) => x.removeAttribute('id'));
        t.append(c); ov.append(t);
      });
      ov.addEventListener('click', (e) => { const t = e.target.closest('.ovt'); if (t) { toggleOverview(false); show(+t.dataset.i); emit(); } });
    }
    const on = open;
    ov.classList.toggle('on', on);
    if (on) {
      ov.querySelectorAll('.ovt').forEach((t, i) => t.classList.toggle('cur', i === cur));
      requestAnimationFrame(() => ov.querySelectorAll('.ovt').forEach((t) => { t.lastElementChild.style.transform = `scale(${t.clientWidth / 1280})`; t.querySelectorAll('figure.chart').forEach((f) => { if (f._w !== f.clientWidth) renderChart(f); }); }));
      const c = ov.querySelector('.ovt.cur'); if (c) c.scrollIntoView({ block: 'center' });
    }
  }

  // ───── 放映辅助：备注面板、翻页按钮、按键提示、黑屏 ─────
  const blank = el('div', { id: 'blank' });
  document.body.append(blank);
  // 演讲者窗口自己不黑：只在顶栏标出观众那边现在是黑屏还是白屏
  function showBlank(v) { blank.className = v; root.classList.toggle('blanked', /\bon\b/.test(v)); root.classList.toggle('blanked-w', /\bw\b/.test(v)); }
  if (MODE === 'main') {
    if (PUBLIC) document.querySelectorAll('.note').forEach((n) => n.remove());
    document.body.append(
      el('div', { id: 'notes' }, '<div class="bar"><span id="n-pg"></span><span id="n-time">00:00</span><span>N 关备注 · T 计时归零 · P 开关演讲者视图</span></div><div id="n-body"></div>'),
      el('div', { id: 'navb' }, '<button type="button" id="prev" aria-label="上一页">‹</button><button type="button" id="next" aria-label="下一页">›</button>'),
      el('div', { id: 'help' }, PUBLIC ? '← → 上一步 / 下一步 · F 全屏 · O 总览' : '← → 上一步 / 下一步 · F 全屏 · O 总览 · P 演讲者视图 · B 黑屏'));
    document.getElementById('prev').onclick = () => step(-1);
    document.getElementById('next').onclick = () => step(1);
    let mv; addEventListener('mousemove', () => { document.body.classList.add('moving'); clearTimeout(mv); mv = setTimeout(() => document.body.classList.remove('moving'), 2500); });
    setInterval(() => { if (t0 === null) return; const s = Math.floor((Date.now() - t0) / 1000); const nt = document.getElementById('n-time'); if (nt) nt.textContent = `${pad(Math.floor(s / 60))}:${pad(s % 60)}`; }, 1000);
  }
  if (MODE === 'presenter') {
    buildPresenter();
    setInterval(() => { const s = Math.floor((Date.now() - t0) / 1000); pv.querySelector('.clock').textContent = `${pad(Math.floor(s / 60))}:${pad(s % 60)}`; pv.querySelector('.now').textContent = new Date().toTimeString().slice(0, 5); }, 1000);
  }
  const setBlank = (c) => { const on = c && !(blank.classList.contains('on') && blank.classList.contains(c === 'w' ? 'w' : 'k')); showBlank(on ? 'on ' + (c === 'w' ? 'w' : 'k') : ''); toOther({ deck: 1, type: 'blank', v: blank.className }); };

  // ───── 按键：翻页笔常发 PageDown/PageUp、F5、Esc、句号或 B（黑屏） ─────
  const NEXT = ['ArrowRight', 'ArrowDown', 'PageDown', ' ', 'Enter'], PREV = ['ArrowLeft', 'ArrowUp', 'PageUp', 'Backspace'];
  if (MODE !== 'mirror') addEventListener('keydown', (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const t = e.target;
    if (t.closest && t.closest('input, textarea, select, [contenteditable="true"]')) return;
    if (t.closest && t.closest('a, button') && (e.key === ' ' || e.key === 'Enter')) return;
    const k = e.key;
    if (blank.classList.contains('on') && (NEXT.includes(k) || PREV.includes(k) || k === 'Escape')) { e.preventDefault(); return setBlank(null); }
    if (ov && ov.classList.contains('on') && (k === 'Escape' || k === 'o' || k === 'O')) { e.preventDefault(); return toggleOverview(false); }
    if (MODE === 'presenter' && (k === 'Escape' || k === 'p' || k === 'P')) { e.preventDefault(); return window.close(); }   // 演讲者窗口里 Esc 或 P 关掉自己
    if (NEXT.includes(k)) { e.preventDefault(); step(1); }
    else if (PREV.includes(k)) { e.preventDefault(); step(-1); }
    else if (k === 'Home') { show(0); emit(); } else if (k === 'End') { show(slides.length - 1); emit(); }
    else if (k === 'F5') { e.preventDefault(); if (!document.fullscreenElement) root.requestFullscreen().catch(() => {}); }
    else if (k === 'f' || k === 'F') { document.fullscreenElement ? document.exitFullscreen() : root.requestFullscreen().catch(() => {}); }
    else if (k === '.' || k === 'b' || k === 'B') setBlank('k');
    else if (k === 'w' || k === 'W') setBlank('w');
    else if (k === 'o' || k === 'O') toggleOverview();
    else if ((k === 'p' || k === 'P') && MODE === 'main' && !PUBLIC) openPresenter();
    else if ((k === 'n' || k === 'N') && MODE === 'main' && !PUBLIC) document.getElementById('notes').classList.toggle('on');
    else if (k === 't' || k === 'T') t0 = Date.now();
  });

  // 页签可以点；打开时没网：有备用截图的在线页换成截图；鼠标离开嵌入页把焦点还给幻灯片
  slides.forEach((s) => s._tabs.forEach((b, i) => b.addEventListener('click', () => { setTab(s, i); b.blur(); emit(); })));
  if (!navigator.onLine) document.querySelectorAll('.box').forEach((b) => { if (b.querySelector('.shot')) b.classList.add('off'); });
  document.querySelectorAll('.box, .panes').forEach((b) => b.addEventListener('mouseleave', () => { if (document.activeElement && ['IFRAME', 'VIDEO'].includes(document.activeElement.tagName)) document.activeElement.blur(); window.focus(); }));
  addEventListener('resize', fit);
  document.addEventListener('fullscreenchange', fit);
  const hashPage = () => Math.min(Math.max((parseInt(location.hash.slice(1), 10) || 1) - 1, 0), slides.length - 1);   // 删过页后 #99 这类越界的停在最后一页
  addEventListener('hashchange', () => { if (MODE === 'main') { show(hashPage(), false); emit(); } });
  fit();
  show(hashPage(), false);

  // 给编辑模式和检查脚本用
  window.deck = { slides, show, step, setTab, paint, settle, emit, renderChart, fit, onShow: (f) => hooks.push(f), get cur() { return cur; } };
})();
