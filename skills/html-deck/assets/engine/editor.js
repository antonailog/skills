// html-deck 编辑模式：只在 scripts/serve.py 打开讲稿时注入，讲稿文件本身不带。
// E 开关 · 点选元素 · 双击改字 · 选中后 Delete 删除 · ⌘Z 撤销 · 列表里回车加一行 · N 打开备注可直接改
// 字号、粗细、颜色在面板上改，[ ] 调字号；按住拖动挪位置（每次 8px，按住 Option 自由拖）。都写成元素的行内样式
// 批注：选中元素就批注这个元素，没选中就批注整页，勾「全局」就不限页面；可粘贴或拖入多张截图
(() => {
  if (/[?&](presenter|mirror)\b/.test(location.search)) return;   // 演讲者视图和它的预览窗口不开编辑
  const PW = 360;
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
  const stage = document.getElementById('stage');
  const page = () => deck.cur + 1;
  // 写操作都带上服务启动时发的口令：别的网页猜不到它，也就没法往讲稿和批注里写东西
  const post = (url, body, type) => fetch(url, { method: 'POST', headers: Object.assign({ 'X-Deck-Token': window.__DECK_TOKEN }, type ? { 'Content-Type': type } : {}), body });
  let on = false, sel = null, hov = null, editing = null, before = '', ver = window.__DECK_VER;
  let comments = [], imgs = [], hist = [], saveT = null, showAll = false, drag = null, dragged = false;
  const COLORS = [['正文', 'var(--ink)'], ['重点', 'var(--accent)'], ['次要', 'var(--mute)']];
  const WEIGHTS = [['常规', '400'], ['粗', '700'], ['特粗', '800']];

  const css = document.createElement('style');
  css.textContent = `
    body.ed-on #stage > .slide.on * { cursor: pointer; }
    body.ed-on #stage > .slide.on iframe { pointer-events: none; }
    body.ed-on .fr { opacity: 1 !important; transform: none !important; pointer-events: auto; }
    body.ed-on .chart .bar, body.ed-on .chart .hbar { transform: none !important; } body.ed-on .chart .ln { stroke-dashoffset: 0 !important; }
    body.ed-on .chart .arc { stroke-dasharray: var(--L) var(--C) !important; } body.ed-on .chart .dot, body.ed-on .chart .val { opacity: 1 !important; }
    body.ed-on .slide.enter { animation: none !important; }
    .ed-hov { outline: 2px dashed #2563eb !important; outline-offset: 2px; }
    .ed-has { background-color: rgba(245, 158, 11, .14) !important; }
    .ed-sel { outline: 3px solid #2563eb !important; outline-offset: 2px; }
    [contenteditable="true"] { outline: 3px solid #16a34a !important; outline-offset: 2px; cursor: text !important; }
    .ed-flash { animation: ed-f 1.4s; } @keyframes ed-f { 0%, 60% { background-color: #fde68a; } }
    body.ed-on #notes { right: ${PW}px; } body.ed-on #navb { right: ${PW + 12}px; }
    body.ed-on #n-body { outline: 1px dashed #777; min-height: 40px; cursor: text; }
    #ed-btn { position: fixed; top: 10px; right: 10px; z-index: 41; font: 600 12px -apple-system, "PingFang SC", sans-serif; background: #2563eb; color: #fff; border: 0; padding: 5px 10px; cursor: pointer; opacity: .55; }
    #ed-btn:hover { opacity: 1; } body.ed-on #ed-btn { display: none; }
    #ed { position: fixed; top: 0; right: 0; bottom: 0; width: ${PW}px; z-index: 40; display: none; flex-direction: column; background: #fafafa; color: #18181b; border-left: 1px solid #d4d4d8; font: 13px/1.55 -apple-system, "PingFang SC", sans-serif; }
    body.ed-on #ed { display: flex; }
    #ed button { font: inherit; cursor: pointer; }
    .ed-top { display: flex; gap: 8px; align-items: center; padding: 10px 12px; background: #18181b; color: #fff; }
    .ed-top span { color: #a1a1aa; font-size: 12px; } .ed-top #ed-st { margin-left: auto; }
    .ed-top #ed-st.bad { color: #fca5a5; } .ed-top #ed-st.ok { color: #86efac; }
    .ed-top button { background: #3f3f46; color: #fff; border: 0; padding: 2px 8px; }
    .ed-tip { padding: 8px 12px; color: #52525b; font-size: 12px; border-bottom: 1px solid #e4e4e7; }
    .ed-new { padding: 10px 12px; border-bottom: 1px solid #e4e4e7; }
    .ed-anchor { font-size: 12px; color: #1d4ed8; margin-bottom: 6px; } .ed-anchor a { color: #71717a; margin-left: 6px; cursor: pointer; }
    #ed-txt { width: 100%; min-height: 72px; font: inherit; padding: 6px 8px; border: 1px solid #d4d4d8; resize: vertical; box-sizing: border-box; }
    #ed-txt.drop { border-color: #2563eb; background: #eff6ff; }
    .ed-imgs { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
    .ed-imgs span { position: relative; } .ed-imgs img { height: 52px; border: 1px solid #d4d4d8; display: block; }
    .ed-imgs b { position: absolute; top: -6px; right: -6px; background: #18181b; color: #fff; width: 16px; height: 16px; font-size: 11px; line-height: 16px; text-align: center; cursor: pointer; border-radius: 50%; }
    .ed-row { display: flex; align-items: center; justify-content: space-between; margin-top: 8px; }
    .ed-row button { background: #2563eb; color: #fff; border: 0; padding: 5px 12px; font-weight: 600; }
    .ed-lh { display: flex; justify-content: space-between; padding: 8px 12px; color: #52525b; font-size: 12px; }
    .ed-list { flex: 1; overflow: auto; padding: 0 12px 12px; }
    .ed-c { background: #fff; border: 1px solid #e4e4e7; padding: 8px 10px; margin-bottom: 8px; cursor: pointer; }
    .ed-c:hover { border-color: #93c5fd; }
    .ed-c-h { display: flex; gap: 6px; align-items: center; font-size: 12px; color: #71717a; }
    .ed-c-h .x { margin-left: auto; background: none; border: 0; color: #a1a1aa; font-size: 15px; padding: 0 2px; }
    .ed-s { font-size: 11px; padding: 0 5px; border-radius: 3px; background: #fef3c7; color: #92400e; white-space: nowrap; }
    .ed-s.s-已改 { background: #dcfce7; color: #166534; } .ed-s.s-有疑问 { background: #fee2e2; color: #991b1b; }
    .ed-c-t { margin-top: 4px; white-space: pre-wrap; }
    .ed-c-r { margin-top: 6px; padding-top: 6px; border-top: 1px dashed #e4e4e7; color: #166534; white-space: pre-wrap; }
    .ed-c .ed-imgs img { height: 44px; }
    body.ed-drag, body.ed-drag * { user-select: none !important; cursor: move !important; }
    .ed-sty { display: none; padding: 8px 12px; border-bottom: 1px solid #e4e4e7; background: #fff; }
    .ed-sty.on { display: block; }
    .ed-sr { display: flex; align-items: center; gap: 6px; margin: 3px 0; font-size: 12px; }
    .ed-sr > span:first-child { width: 30px; color: #71717a; }
    .ed-sr button { background: #f4f4f5; border: 1px solid #d4d4d8; padding: 1px 8px; min-width: 26px; }
    .ed-sr button.cur { border-color: #2563eb; background: #eff6ff; color: #1d4ed8; }
    .ed-sr button:disabled { opacity: .4; cursor: default; }
    .ed-sr button.sw { width: 22px; min-width: 0; height: 20px; padding: 0; }
    .ed-sr button.sw.cur { outline: 2px solid #2563eb; outline-offset: 1px; }
    .ed-sr input[type=color] { width: 26px; height: 22px; padding: 0; border: 1px solid #d4d4d8; background: none; cursor: pointer; }
    .ed-sr b { min-width: 46px; text-align: center; font-weight: 600; }
    .ed-sr .ed-k { color: #a1a1aa; } .ed-sr .ed-r { margin-left: auto; }
    .ed-sty .ed-no { color: #a1a1aa; font-size: 12px; }`;
  document.head.appendChild(css);

  const btn = document.createElement('button');
  btn.id = 'ed-btn'; btn.textContent = '编辑（E）'; btn.onclick = () => toggle();
  const panel = document.createElement('div');
  panel.id = 'ed';
  panel.innerHTML = `
    <div class="ed-top"><b>编辑模式</b><span id="ed-pg"></span><span id="ed-st">未改动</span><button type="button" id="ed-x">退出 E</button></div>
    <div class="ed-tip">点选元素 · 双击改字 · 按住拖动挪位置（Option 自由拖）· [ ] 调字号 · Delete 删除 · ⌘Z 撤销 · 列表里回车加一行 · N 打开备注可直接改 · 改动自动保存</div>
    <div class="ed-sty" id="ed-sty">
      <div class="ed-sr" data-font><span>字号</span><button type="button" data-fs="-2">−</button><b id="ed-fs"></b><button type="button" data-fs="2">+</button><span class="ed-k">[ ]</span></div>
      <div class="ed-sr" data-font><span>粗细</span>${WEIGHTS.map(([n, w]) => `<button type="button" data-fw="${w}">${n}</button>`).join('')}</div>
      <div class="ed-sr" data-font><span>颜色</span>${COLORS.map(([n, c]) => `<button type="button" class="sw" title="${n}" data-c="${c}" style="background:${c}"></button>`).join('')}<input type="color" id="ed-cc" title="其他颜色"></div>
      <div class="ed-no" id="ed-nofont">图表里的字改不了字号和颜色，整张图可以拖动</div>
      <div class="ed-sr"><span>位置</span><b id="ed-pos"></b><button type="button" id="ed-up" title="选中外面一层，好整块拖动">选外层</button><button type="button" class="ed-r" id="ed-rs">恢复原样</button></div>
    </div>
    <div class="ed-new">
      <div class="ed-anchor" id="ed-anchor"></div>
      <textarea id="ed-txt" placeholder="写批注，可粘贴或拖入截图（可多张）。⌘Enter 提交"></textarea>
      <div class="ed-imgs" id="ed-imgs"></div>
      <div class="ed-row"><label><input type="checkbox" id="ed-g"> 全局（跨页、不限本页）</label><button type="button" id="ed-add">添加批注</button></div>
    </div>
    <div class="ed-lh"><span id="ed-cnt"></span><label><input type="checkbox" id="ed-all"> 看全部</label></div>
    <div class="ed-list" id="ed-list"></div>`;
  document.body.append(btn, panel);

  // ───── 元素定位 ─────
  const slidesAll = () => deck.slides;
  function path(el) {
    const s = el.closest('.slide'), chain = [];
    for (let n = el; n !== s; n = n.parentElement) chain.unshift([...n.parentElement.children].indexOf(n));
    return slidesAll().indexOf(s) + ':' + chain.join('.');
  }
  function resolve(p) {
    const [si, rest] = p.split(':');
    let n = slidesAll()[+si];
    for (const i of (rest ? rest.split('.') : [])) { n = n && n.children[+i]; }
    return n || null;
  }
  function snippet(el, len = 40) {
    if (el.closest('svg') || el.matches('figure.chart')) return '图表';
    if (el.tagName === 'IFRAME' || el.classList.contains('box')) return '嵌入页';
    return (el.innerText || el.textContent || el.tagName).trim().replace(/\s+/g, ' ').slice(0, len) || el.tagName;
  }
  function pick(e) {
    let t = e.target;
    if (!t.closest || !t.closest('#stage > .slide.on')) return null;
    if (t.closest('svg')) { t = t.closest('svg'); if (t.hasAttribute('data-gen')) t = t.parentElement; }   // 引擎画的图表、二维码：选中外框，保存时才留得住
    return t.classList.contains('slide') ? null : t;
  }
  function blockOf(t) {
    while (t && !t.classList.contains('slide') && getComputedStyle(t).display === 'inline') t = t.parentElement;
    return t && !t.classList.contains('slide') ? t : null;
  }

  // ───── 选中、改字、删除 ─────
  function select(el) {
    if (sel) sel.classList.remove('ed-sel');
    sel = el;
    if (el) el.classList.add('ed-sel');
    if (editing && el !== editing && !(el && editing.contains(el))) finishEdit();
    renderAnchor(); renderSty();
  }
  function startEdit(el) {
    finishEdit();
    const s = getSelection(), r = s.rangeCount ? s.getRangeAt(0).cloneRange() : null;
    editing = el; before = el.innerHTML;
    el.contentEditable = 'true'; el.spellcheck = false; el.focus();
    if (r && el.contains(r.startContainer)) { s.removeAllRanges(); s.addRange(r); }
    select(el);
  }
  function finishEdit() {
    if (!editing) return;
    const el = editing; editing = null;
    el.removeAttribute('contenteditable'); el.removeAttribute('spellcheck');
    if (el.innerHTML !== before) dirty();
  }
  function del(el) {
    if (el === editing) finishEdit();
    hist.push({ el, parent: el.parentNode, next: el.nextSibling });
    el.remove(); select(null); dirty();
  }
  function undo() {
    const r = hist.pop();
    if (!r) return;
    if (r.parent) r.parent.insertBefore(r.el, r.next && r.next.parentNode === r.parent ? r.next : null);
    else if (r.batch) r.batch.forEach((b) => setAttr(b.el, b.style));
    else setAttr(r.el, r.style);
    select(r.el); dirty();
  }

  // ───── 字号、粗细、颜色、位置（行内样式） ─────
  const isSvg = (el) => !!el.closest('svg');
  const setAttr = (el, v) => (v ? el.setAttribute('style', v) : el.removeAttribute('style'));
  // 选中的是一组（自己没有字，只有子元素）时，字号、粗细、颜色改到组里每一段有字的元素上
  const ownText = (n) => [...n.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim());
  function textEls(el) {
    if (ownText(el)) return [el];
    const r = [...el.querySelectorAll('*')].filter((n) => ownText(n) && !n.closest('svg') && !r0(n, el));
    return r.length ? r : [el];
  }
  // 已经有祖先在名单里的（比如 li 里的 b）不再单独改，跟着祖先走
  const r0 = (n, root) => { for (let p = n.parentElement; p && p !== root; p = p.parentElement) if (ownText(p)) return true; return false; };
  function restyle(el, fn, targets = [el]) {
    hist.push({ el, batch: targets.map((t) => ({ el: t, style: t.getAttribute('style') })) });
    targets.forEach((t) => { fn(t.style, t); if (!t.getAttribute('style')) t.removeAttribute('style'); });
    dirty(); renderSty();
  }
  function fontStep(d) {
    if (!sel || isSvg(sel)) return;
    restyle(sel, (s, t) => { s.fontSize = Math.max(8, Math.round(parseFloat(getComputedStyle(t).fontSize)) + d) + 'px'; }, textEls(sel));
  }
  const offset = (el) => { const [x = 0, y = 0] = (el.style.translate || '').split(' ').map(parseFloat); return [x || 0, y || 0]; };
  function renderSty() {
    const box = $('#ed-sty');
    box.classList.toggle('on', !!sel);
    if (!sel) return;
    const svg = isSvg(sel), ts = svg ? [sel] : textEls(sel), cs = getComputedStyle(ts[0]);
    box.querySelectorAll('[data-font]').forEach((r) => { r.style.display = svg ? 'none' : ''; });
    $('#ed-nofont').style.display = svg ? '' : 'none';
    const px = [...new Set(ts.map((t) => Math.round(parseFloat(getComputedStyle(t).fontSize))))].sort((a, b) => a - b);
    $('#ed-fs').textContent = px.length > 1 ? `${px[0]}–${px[px.length - 1]}px` : px[0] + 'px';
    box.querySelectorAll('[data-fw]').forEach((b) => b.classList.toggle('cur', String(cs.fontWeight) === b.dataset.fw));
    const probe = document.createElement('i'); sel.parentElement.appendChild(probe);
    box.querySelectorAll('[data-c]').forEach((b) => { probe.style.color = b.dataset.c; b.classList.toggle('cur', getComputedStyle(probe).color === cs.color); });
    probe.remove();
    const [x, y] = offset(sel);
    $('#ed-pos').textContent = x || y ? `偏移 ${x}, ${y}` : '原位';
    $('#ed-up').disabled = !sel.parentElement || sel.parentElement.classList.contains('slide');
  }

  // ───── 保存 ─────
  const st = (t, c = '') => { const e = $('#ed-st'); e.textContent = t; e.className = c; };
  function dirty() { st('未保存'); clearTimeout(saveT); saveT = setTimeout(save, 800); }
  async function save() {
    clearTimeout(saveT);
    deck.settle();   // 数字滚动停在最终值，不把滚到一半的数存进文件
    const c = stage.cloneNode(true);
    c.querySelectorAll('.ed-hov, .ed-sel, .ed-has, .ed-flash').forEach((n) => n.classList.remove('ed-hov', 'ed-sel', 'ed-has', 'ed-flash'));
    c.querySelectorAll('[contenteditable]').forEach((n) => { n.removeAttribute('contenteditable'); n.removeAttribute('spellcheck'); });
    c.querySelectorAll('.slide.on').forEach((n) => n.classList.remove('on'));
    c.querySelectorAll('iframe[data-src]').forEach((n) => n.removeAttribute('src'));
    c.querySelectorAll('.box.off').forEach((n) => n.classList.remove('off'));   // 断网时临时换成截图的标记
    // 引擎画的图表、二维码，翻页动效留下的标记，都不写进文件
    c.querySelectorAll('[data-gen]').forEach((n) => n.remove());
    c.querySelectorAll('.play, .enter, .back, .now').forEach((n) => n.classList.remove('play', 'enter', 'back', 'now'));
    // 页码是讲稿打开时自动填的，不写进文件
    c.querySelectorAll('.pg').forEach((pg) => { pg.textContent = ''; });
    // 分步出现的标记是讲稿打开时加的，不写进文件
    c.querySelectorAll('.fr').forEach((n) => { n.classList.remove('fr', 'in'); n.removeAttribute('data-fr'); });
    // 页签回到第一个，免得把你当时点开的那个存成默认
    c.querySelectorAll('.tabs').forEach((t) => [...t.children].forEach((x, j) => x.classList.toggle('cur', j === 0)));
    c.querySelectorAll('.panes').forEach((ps) => [...ps.children].forEach((x, j) => x.classList.toggle('cur', j === 0)));
    c.querySelectorAll('[class=""]').forEach((n) => n.removeAttribute('class'));
    try {
      const r = await post('/__api/save', JSON.stringify({ stage: c.innerHTML, ver }));
      const j = await r.json();
      if (j.ok) { ver = j.ver; st('已保存 ' + new Date().toTimeString().slice(0, 5), 'ok'); }
      else if (j.err === 'changed') st('文件在别处被改过，刷新页面后再改（这次没存上）', 'bad');
      else st('保存失败：' + j.err, 'bad');
    } catch (e) { st('保存失败：服务没开', 'bad'); }
  }

  // ───── 备注（N 面板）直接改 ─────
  const nb = $('#n-body');
  nb.addEventListener('input', () => {
    if (!on) return;
    const s = slidesAll()[deck.cur];
    let n = s.querySelector('.note');
    if (!n) { n = document.createElement('aside'); n.className = 'note'; s.appendChild(n); }
    n.innerHTML = nb.innerHTML; dirty();
  });

  // ───── 批注 ─────
  async function loadComments() {
    try { comments = await (await fetch('/__api/comments')).json(); } catch (e) {}
    render();
  }
  async function upload(file) {
    const r = await post('/__api/image', file, file.type);
    imgs.push((await r.json()).path); renderImgs();
  }
  async function addComment() {
    const text = $('#ed-txt').value.trim();
    if (!text && !imgs.length) return;
    const g = $('#ed-g').checked;
    const c = {
      id: Date.now().toString(36), time: new Date().toLocaleString('zh-CN', { hour12: false }),
      page: g ? null : page(), scope: g ? '全局' : sel ? '元素' : '本页',
      target: !g && sel ? { path: path(sel), text: snippet(sel, 80) } : null,
      text, images: imgs.slice(), status: '待处理', reply: '',
    };
    comments = await (await post('/__api/comments/add', JSON.stringify(c))).json();
    imgs = []; $('#ed-txt').value = ''; $('#ed-g').checked = false; select(null); renderImgs(); render();
  }
  const imgHTML = (list, rm) => list.map((p, i) => `<span><img src="/__notes/${encodeURI(p)}" alt="">${rm ? `<b data-i="${i}">×</b>` : ''}</span>`).join('');
  function renderImgs() { $('#ed-imgs').innerHTML = imgHTML(imgs, true); }
  function renderAnchor() {
    const g = $('#ed-g').checked;
    $('#ed-anchor').innerHTML = g ? '批注对象：全局（不限页面）'
      : sel ? `批注对象：第 ${page()} 页 ·「${esc(snippet(sel))}」<a id="ed-clr">改成整页</a>` : `批注对象：第 ${page()} 页（整页）· 先点选元素可批注到元素`;
  }
  function render() {
    $('#ed-pg').textContent = `第 ${page()} / ${slidesAll().length} 页`;
    renderAnchor();
    document.querySelectorAll('.ed-has').forEach((n) => n.classList.remove('ed-has'));
    if (on) comments.forEach((c) => { if (c.page === page() && c.target && c.status !== '已改') { const n = resolve(c.target.path); if (n) n.classList.add('ed-has'); } });
    const list = comments.filter((c) => showAll || c.page === page() || c.scope === '全局');
    const todo = comments.filter((c) => c.status === '待处理').length;
    $('#ed-cnt').textContent = `${showAll ? '全部' : '本页和全局'} ${list.length} 条 · 共 ${comments.length} 条，待处理 ${todo}`;
    $('#ed-list').innerHTML = list.map((c) => `<div class="ed-c" data-id="${c.id}">
      <div class="ed-c-h"><span class="ed-s s-${esc(c.status)}">${esc(c.status)}</span><span>${c.page ? '第 ' + c.page + ' 页' : '全局'}${c.target ? ' ·「' + esc(c.target.text.slice(0, 24)) + '」' : ''}</span><button type="button" class="x" title="删除这条">×</button></div>
      ${c.text ? `<div class="ed-c-t">${esc(c.text)}</div>` : ''}${c.images.length ? `<div class="ed-imgs">${imgHTML(c.images)}</div>` : ''}
      ${c.reply ? `<div class="ed-c-r">${esc(c.reply)}</div>` : ''}</div>`).join('');
  }

  // ───── 开关、布局 ─────
  function layout() {
    if (!on) { stage.style.left = ''; deck.fit(); return; }
    const W = innerWidth - PW, k = Math.min(W / 1280, innerHeight / 720);
    stage.style.left = W / 2 + 'px';
    stage.style.transform = `translate(-50%, -50%) scale(${k})`;
  }
  function toggle() {
    on = !on;
    document.body.classList.toggle('ed-on', on);
    if (!on) { finishEdit(); select(null); if (hov) hov.classList.remove('ed-hov'); hov = null; }
    nb.contentEditable = on ? 'true' : 'false';
    layout(); if (on) loadComments(); else render();
  }
  addEventListener('resize', layout);
  addEventListener('focus', () => { if (on && !$('#ed-txt').value) loadComments(); });

  deck.onShow(() => {
    finishEdit(); select(null);
    if (on) { nb.contentEditable = 'true'; render(); }
  });

  // ───── 事件 ─────
  document.addEventListener('mouseover', (e) => {
    if (!on) return;
    const t = pick(e);
    if (t === hov) return;
    if (hov) hov.classList.remove('ed-hov');
    hov = t; if (t) t.classList.add('ed-hov');
  }, true);
  document.addEventListener('click', (e) => {
    if (!on || e.target.closest('#ed, #notes, #navb, #ed-btn')) return;
    if (dragged) { dragged = false; e.preventDefault(); e.stopPropagation(); return; }
    const t = pick(e);
    if (editing && t && editing.contains(t)) return;
    e.preventDefault(); e.stopPropagation();
    select(t);
  }, true);

  // 拖动：按下后移动超过 4px 才算拖，否则还是单击选中；位置记成相对原位的偏移（CSS translate）
  document.addEventListener('dragstart', (e) => { if (on && e.target.closest && e.target.closest('#stage')) e.preventDefault(); }, true);
  document.addEventListener('pointerdown', (e) => {
    dragged = false;
    if (!on || e.button !== 0 || e.target.closest('#ed, #notes, #navb, #ed-btn')) return;
    const t = pick(e);
    if (!t || (editing && editing.contains(t))) return;
    // 行内文字挪不动，换成它所在的块；图、图表、嵌入页本身就能挪
    const base = sel && sel.contains(t) ? sel : t;
    const el = /^(svg|IMG|VIDEO|IFRAME)$/.test(base.tagName) ? base : blockOf(base);
    if (!el) return;
    const [x0, y0] = offset(el);
    drag = { el, sx: e.clientX, sy: e.clientY, x0, y0, moved: false, before: el.getAttribute('style') };
  }, true);
  addEventListener('pointermove', (e) => {
    if (!drag) return;
    const dx = e.clientX - drag.sx, dy = e.clientY - drag.sy;
    if (!drag.moved) {
      if (Math.hypot(dx, dy) < 4) return;
      drag.moved = true; finishEdit(); select(drag.el);
      document.body.classList.add('ed-drag'); getSelection().removeAllRanges();
    }
    const k = stage.getBoundingClientRect().width / stage.offsetWidth, g = e.altKey ? 1 : 8;
    const x = Math.round((drag.x0 + dx / k) / g) * g, y = Math.round((drag.y0 + dy / k) / g) * g;
    drag.el.style.translate = x || y ? `${x}px ${y}px` : '';
    renderSty();
  }, true);
  function endDrag() {
    if (!drag) return;
    const d = drag; drag = null;
    if (!d.moved) return;
    document.body.classList.remove('ed-drag');
    if (!d.el.getAttribute('style')) d.el.removeAttribute('style');
    if (d.el.getAttribute('style') !== d.before) { hist.push({ el: d.el, style: d.before }); dirty(); }
    dragged = true;
  }
  addEventListener('pointerup', endDrag, true);
  addEventListener('pointercancel', endDrag, true);
  document.addEventListener('dblclick', (e) => {
    if (!on) return;
    const t = pick(e);
    if (!t || t.closest('svg, .box')) return;
    const b = blockOf(t);
    if (b) startEdit(b);
  }, true);
  document.addEventListener('input', (e) => { if (on && editing && editing.contains(e.target)) dirty(); }, true);
  addEventListener('beforeunload', (e) => { if ($('#ed-st') && $('#ed-st').textContent === '未保存') { e.preventDefault(); e.returnValue = ''; } });

  addEventListener('keydown', (e) => {
    const k = e.key, mod = e.metaKey || e.ctrlKey, t = e.target;
    const typing = t.isContentEditable || /^(TEXTAREA|INPUT)$/.test(t.tagName);
    if (mod && k === 's') { e.preventDefault(); e.stopPropagation(); if (on) { finishEdit(); save(); } return; }
    if (typing) {
      if (editing && t === editing) {
        if (k === 'Escape') { e.preventDefault(); finishEdit(); }
        else if (k === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          if (editing.tagName === 'LI') { const li = document.createElement('li'); li.className = editing.className; editing.after(li); startEdit(li); }
          else finishEdit();
        }
      }
      if (t.id === 'ed-txt' && k === 'Enter' && mod) { e.preventDefault(); addComment(); }
      e.stopPropagation(); return;
    }
    if ((k === 'e' || k === 'E') && !mod && !e.altKey) { e.preventDefault(); e.stopPropagation(); toggle(); return; }
    if (!on) return;
    if ((k === 'Delete' || k === 'Backspace') && sel) { e.preventDefault(); e.stopPropagation(); del(sel); return; }
    if (mod && k === 'z') { e.preventDefault(); e.stopPropagation(); undo(); return; }
    if ((k === '[' || k === ']') && sel && !mod) { e.preventDefault(); e.stopPropagation(); fontStep(k === ']' ? 2 : -2); return; }
    if (k === 'Escape') select(null);
  }, true);

  $('#ed-sty').addEventListener('click', (e) => {
    const b = e.target.closest('button'); if (!b || !sel) return;
    if (b.dataset.fs) fontStep(+b.dataset.fs);
    else if (b.dataset.fw) restyle(sel, (s) => { s.fontWeight = b.dataset.fw; }, textEls(sel));
    else if (b.dataset.c) restyle(sel, (s) => { s.color = b.dataset.c; }, textEls(sel));
    else if (b.id === 'ed-up') select(sel.parentElement);
    else if (b.id === 'ed-rs') restyle(sel, (s) => { ['font-size', 'font-weight', 'color', 'translate'].forEach((p) => s.removeProperty(p)); }, [sel, ...sel.querySelectorAll('[style]')]);
  });
  $('#ed-cc').addEventListener('change', (e) => { if (sel) restyle(sel, (s) => { s.color = e.target.value; }, textEls(sel)); });
  $('#ed-x').onclick = () => toggle();
  $('#ed-add').onclick = addComment;
  $('#ed-g').onchange = renderAnchor;
  $('#ed-all').onchange = (e) => { showAll = e.target.checked; render(); };
  $('#ed-anchor').addEventListener('click', (e) => { if (e.target.id === 'ed-clr') select(null); });
  $('#ed-imgs').addEventListener('click', (e) => { if (e.target.dataset.i) { imgs.splice(+e.target.dataset.i, 1); renderImgs(); } });
  const ta = $('#ed-txt');
  ta.addEventListener('paste', (e) => {
    const fs = [...e.clipboardData.items].filter((i) => i.type.startsWith('image/')).map((i) => i.getAsFile());
    if (fs.length) { e.preventDefault(); fs.forEach(upload); }
  });
  ta.addEventListener('dragover', (e) => { e.preventDefault(); ta.classList.add('drop'); });
  ta.addEventListener('dragleave', () => ta.classList.remove('drop'));
  ta.addEventListener('drop', (e) => {
    ta.classList.remove('drop');
    const fs = [...e.dataTransfer.files].filter((f) => f.type.startsWith('image/'));
    if (fs.length) { e.preventDefault(); fs.forEach(upload); }
  });
  $('#ed-list').addEventListener('click', async (e) => {
    const box = e.target.closest('.ed-c'); if (!box) return;
    const c = comments.find((x) => x.id === box.dataset.id); if (!c) return;
    if (e.target.classList.contains('x')) {
      if (!confirm('删除这条批注？')) return;
      comments = await (await post('/__api/comments/del', JSON.stringify({ id: c.id }))).json();
      return render();
    }
    if (e.target.tagName === 'IMG') return open(e.target.src);
    if (c.page && c.page !== page()) { deck.show(c.page - 1); deck.emit(); }
    const n = c.target && resolve(c.target.path);
    if (n) { n.classList.remove('ed-flash'); void n.offsetWidth; n.classList.add('ed-flash'); }
  });
  render();
})();
