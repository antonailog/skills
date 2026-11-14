(() => {
  'use strict';
  const ACTION_TAGS = Object.freeze(Object.fromEntries([
    ['read', '读取', '--t-read'], ['search', '查找', '--t-read'], ['filter', '过滤', '--t-read'], ['list', '列出', '--t-read'],
    ['write', '写入', '--t-write'], ['edit', '编辑', '--t-write'], ['exec', '执行', '--t-run'], ['fetch', '抓取', '--t-run'],
    ['spawn', '调用', '--t-task'], ['return', '返回', '--t-task'], ['user', '用户', '--t-task'], ['reminder', '提醒', '--t-auto'],
    ['reply', '回复', '--t-img'], ['think', '思考', '--t-img'], ['inputs', '输入', '--ink2']
  ].map(([key, text, color]) => [key, {text, color}])));
  const CATEGORY_COLORS = {system:'--t-task', tools:'--t-run', injected:'--t-auto', task:'--accent', history:'--t-read', previous:'--t-read', current:'--t-write', model:'--t-img', reminders:'--ink3'};
  const actionTag = value => ACTION_TAGS[typeof value === 'string' ? value : value.operation] || ACTION_TAGS.exec;
  const num = value => value == null ? '未知' : Number(value).toLocaleString('en-US');
  const join = values => values.filter(v => v !== '' && v != null).join(' · ');
  const basename = path => (path || '').replace(/\/$/, '').split('/').pop();
  const absolutePath = path => typeof path === 'string' && path.startsWith('/') && !path.includes('\0');
  const isSegmented = node => node.timeline_mode ? node.timeline_mode === 'segments' : !!node.agent_id;
  const eventCharacterCount = event => event.characters > 0 ? num(event.characters) : '';
  // 运行环境自己的文件：会话记录、工具输出存档、临时目录、依赖、系统目录。其余本机文件都算用户的，文件名用橙红色。
  const SYSTEM_PATH = /\/(?:tool-results|scratchpad|node_modules|subagents)\/|^\/(?:private\/tmp|tmp|var\/folders|usr|System|Library|opt|bin|sbin)\/|\.jsonl$/;
  const isUserFile = path => absolutePath(path) && !SYSTEM_PATH.test(path);
  const GLOSSARY = [
    ['主 Agent', '你在对话框里直接对话的那个 Claude。'],
    ['子 Agent', '主 Agent 派出去做一件具体工作的另一个 Claude，有自己独立的上下文。名字是主 Agent 给这件工作起的。'],
    ['上下文', '这个 Agent 第一次向模型发请求时已经带着的内容：系统提示词、工具定义、注入内容，以及任务提示词（子 Agent）或之前的对话（主 Agent）。'],
    ['系统提示词', 'Claude Code 自带的总说明。'],
    ['工具定义', '它能用哪些工具（Read、Bash、Write……）以及每个工具怎么用。'],
    ['注入内容', 'Claude Code 自动放进去的文件和信息，比如 CLAUDE.md、MEMORY.md、skill 列表、环境信息。'],
    ['任务提示词', '主 Agent 派活时写给子 Agent 的那段话。'],
    ['之前的对话', '圈定范围开始之前，这个会话里已有的对话内容。'],
    ['N 次操作 → 写入 X', '两次写入文档之间的所有操作，归到结尾那次写入下面，点开按时间看每一步。写代码文件、图片不算写入文档。'],
    ['代码与命令 ×N', '连着的几次执行、列出和代码文件的读写，合成一行，点开看每一条。'],
    ['第 N 轮', '这个 Agent 第 N 次向模型发请求：把到这一刻为止的全部内容发过去，模型回一次话。点开一行，中间最下面列出这一轮的模型、时间和模型说的话；每轮之间有一条细线。主 Agent 和子 Agent 分开计数。'],
    ['用户', '你发的消息。'], ['读取', '把文件内容读进来，全文或一部分。'], ['查找', '在文件里搜关键词，只拿到匹配的那几行。'],
    ['过滤', '用 awk 按条件挑出文件里的一部分。'], ['列出', '看一个目录里有哪些文件。'], ['执行', '运行一个命令或脚本，拿回它的输出。'],
    ['写入', '新建一个文件，或者整个覆盖重写。'], ['编辑', '改一个已有文件里的某一段。'], ['抓取', '去网上取一个网页。'],
    ['调用', '主 Agent 派出一个子 Agent。'], ['返回', '子 Agent 把结果交回给主 Agent。'], ['提醒', '运行途中 Claude Code 自动插进来的一句话，比如某个文件被改过了。'],
    ['橙红色文件名', '你自己的文件，或者这次被改过的文件，会影响结果。普通颜色是运行时临时生成的东西。'],
    ['右侧数字', '这一项的长度（字符）：读取是读到多少，写入是写了多少，调用是任务提示词多长。']
  ];
  function shortName(event, data) {
    const name = event.display_name || '';
    if (event.operation === 'list') {
      const command = (event.item_ids || []).map(id => data.items?.[id]?.command).find(Boolean) || name;
      // 只看 ls 那一段的第一行，heredoc 正文、重定向之后的内容都不算参数
      const ls = (command.split(/[;&|\n]+/).find(part => part.trim().startsWith('ls')) || command).split('<<')[0];
      const dirs = [...new Set(ls.trim().split(/\s+/).slice(1).map(t => t.replace(/^["']|["']$/g, ''))
        .filter(t => t && !t.startsWith('-') && !/^\d*>|^\/dev\/null$|[<>`$]/.test(t)).map(t => t.replace(/\/$/, '').split('/').pop() + '/'))];
      if (!dirs.length) return name.length > 28 ? name.slice(0, 28) + '…' : name;
      return dirs.slice(0, 4).join('、') + (dirs.length > 4 ? '…' : '');
    }
    if (event.operation === 'exec' && name.length > 28) return name.slice(0, 28) + '…';
    return name;
  }

  function traceGraph(data) {
    const nodes = new Map(data.nodes.map(node => [node.id, node]));
    const allowed = new Set(data.trace_overview?.edge_ids || data.edges.map(edge => edge.id));
    const edges = data.edges.filter(edge => allowed.has(edge.id) && nodes.has(edge.source_node_id) && nodes.has(edge.target_node_id));
    const ordered = [], seen = new Set();
    function visit(node) {
      if (seen.has(node.id)) return;
      seen.add(node.id); ordered.push(node);
      const calls = edges.filter(edge => edge.kind === 'dispatch' && edge.source_node_id === node.id);
      calls.sort((a, b) => (data.events[a.source_event_id]?.request_number || 0) - (data.events[b.source_event_id]?.request_number || 0));
      for (const edge of calls) visit(nodes.get(edge.target_node_id));
    }
    for (const node of data.nodes.filter(node => !nodes.has(node.parent_id))) visit(node);
    for (const node of data.nodes) visit(node);
    return {nodes:ordered, edges};
  }

  function resolve(data, ref) {
    if (!ref) return null;
    let value = data.sources[ref.source_id];
    for (const part of (ref.pointer || '').split('/').slice(1)) value = value?.[part.replace(/~1/g, '/').replace(/~0/g, '~')];
    return typeof value === 'string' && (ref.start != null || ref.end != null) ? Array.from(value).slice(ref.start || 0, ref.end).join('') : value;
  }
  function contentText(value) {
    if (typeof value === 'string') return value;
    if (Array.isArray(value)) return value.map(contentText).join('');
    if (!value || typeof value !== 'object' || ['image', 'document'].includes(value.type)) return '';
    if ('content' in value) return contentText(value.content);
    return value.text || value.thinking || '';
  }
  function shouldRenderMarkdown(options = {}) {
    if (options.output_truncated || options.failed || options.shared_with?.length) return false;
    if (['user', 'task', 'spawn', 'return', 'reply', 'think'].includes(options.operation)) return true;
    if (!/\.md$/i.test(options.path || '')) return false;
    if (['search', 'filter', 'exec', 'list', 'fetch', 'reminder'].includes(options.operation)) return false;
    if (options.version === 'current' || ['write', 'edit'].includes(options.operation)) return true;
    const range = options.read_range || {};
    if ((range.selectors || []).some(s => s.bytes != null || ['grep', 'rg', 'awk', 'find'].includes(s.method))) return false;
    // Several disjoint sed ranges are not a continuous Markdown document.
    if ((range.selectors || []).some(s => s.method === 'sed' && (!s.ranges?.length || s.ranges.some((r, i) => i && r[0] > s.ranges[i - 1][1] + 1)))) return false;
    return options.operation === 'read' && (range.kind === 'full' || (range.kind === 'partial' && !!range.selectors?.length));
  }
  function fileMenuActions(path) {
    if (!absolutePath(path)) return [];
    return [
      {id:'reveal', label:'在 Finder 中显示', href:`agent-context-trace://reveal?path=${encodeURIComponent(path)}`},
      {id:'vscode', label:'在 VS Code 中打开', href:`vscode://file${path.split('/').map(encodeURIComponent).join('/')}`},
      {id:'copy', label:'复制路径', href:'#copy-path', path}
    ];
  }
  const referenceHref = ref => ref.kind === 'dir' ? fileMenuActions(ref.path).find(action => action.id === 'vscode')?.href : '#file';
  function activateReference(ref, actions, command = false) {
    if (!absolutePath(ref.path)) return;
    if (command) actions.navigate(fileMenuActions(ref.path)[0].href);
    else if (ref.kind === 'dir') actions.navigate(referenceHref(ref));
    else actions.openFile(ref.path);
  }
  function referenceCandidates(data, value, context = {}) {
    const text = contentText(value);
    const owners = new Set(context.ownerIds || []);
    const candidates = [];
    for (const ref of data.file_references || []) {
      if (context.nodeId && ref.node_id !== context.nodeId) continue;
      const original = resolve(data, ref.text_ref);
      if (typeof original !== 'string') continue;
      const sameSource = original === text;
      const sameOwner = (ref.owner_ids || []).some(id => owners.has(id));
      const sameFile = context.sourcePath && ref.source_path === context.sourcePath;
      if (!(sameOwner || sameFile || (sameSource && (context.nodeId || context.sourcePath)))) continue;
      if (context.sourcePath && ref.source_path && ref.source_path !== context.sourcePath) continue;
      const literal = Array.from(original).slice(ref.start, ref.end).join('');
      if (literal && text.includes(literal) && absolutePath(ref.path)) candidates.push({text:literal, path:ref.path, kind:ref.kind || 'file'});
    }
    // The same spelling may mean different files in different source contexts.
    const choices = new Map();
    for (const ref of candidates) {
      if (!choices.has(ref.text)) choices.set(ref.text, new Map());
      choices.get(ref.text).set(`${ref.kind}:${ref.path}`, ref);
    }
    return [...choices.values()].filter(paths => paths.size === 1).map(paths => [...paths.values()][0]).sort((a, b) => b.text.length - a.text.length);
  }
  function referenceMatches(text, references) {
    const matches = [];
    let offset = 0;
    while (offset < text.length) {
      let next = null;
      for (const ref of references) {
        if (!ref.text) continue;
        let start = text.indexOf(ref.text, offset);
        // A recorded directory mention elsewhere in the same paragraph must
        // not become a prefix link inside a longer file/directory token.
        const boundary = char => !char || /[\s`"'<>\[\](){}，。；：！？、「」『』“”‘’|=*,;:!]/u.test(char);
        const endBoundary = end => boundary(text[end]) || (text[end] === '.' && boundary(text[end + 1]));
        while (start >= 0 && ref.kind === 'dir' &&
          (!boundary(text[start - 1]) || !endBoundary(start + ref.text.length))) start = text.indexOf(ref.text, start + 1);
        if (start >= 0 && (!next || start < next.start || (start === next.start && ref.text.length > next.text.length))) next = {...ref, start};
      }
      if (!next) break;
      matches.push({...next, end:next.start + next.text.length});
      offset = next.start + next.text.length;
    }
    return matches;
  }
  function wrapReferences(root, references) {
    const doc = root.ownerDocument;
    const walker = doc.createTreeWalker(root, 4); // SHOW_TEXT; includes code and pre.
    const texts = [];
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (!node.parentElement?.closest('a,script,style')) texts.push(node);
    }
    for (const node of texts) {
      const matches = referenceMatches(node.nodeValue, references);
      if (!matches.length) continue;
      const fragment = doc.createDocumentFragment();
      let end = 0;
      for (const match of matches) {
        fragment.append(doc.createTextNode(node.nodeValue.slice(end, match.start)));
        const link = doc.createElement('a');
        link.className = 'ref'; link.dataset.path = match.path; link.dataset.kind = match.kind || 'file';
        link.href = referenceHref(match); link.textContent = match.text; link.title = match.path;
        fragment.append(link); end = match.end;
      }
      fragment.append(doc.createTextNode(node.nodeValue.slice(end)));
      node.replaceWith(fragment);
    }
    return root;
  }
  function createMarkdown(markdownit) {
    const md = markdownit({html:false, linkify:false});
    const escape = md.utils.escapeHtml;
    md.core.ruler.after('block', 'source_lines', state => {
      for (const token of state.tokens) {
        if (!token.block || !token.map || token.nesting === -1) continue;
        token.attrSet('data-line-start', String(token.map[0] + 1));
        token.attrSet('data-line-end', String(token.map[1]));
        if ((state.env.readRanges || []).some(r => r.start <= token.map[1] && r.end >= token.map[0] + 1)) token.attrJoin('class', 'read-covered');
      }
    });
    for (const rule of ['fence', 'code_block']) md.renderer.rules[rule] = (tokens, idx, options, env, self) => {
      const token = tokens[idx];
      return `<pre${self.renderAttrs(token)}><code>${escape(token.content)}</code></pre>\n`;
    };
    // Never create a remote image request, even one that CSP would then block.
    md.renderer.rules.image = (tokens, idx, options, env) => {
      const token = tokens[idx], src = token.attrGet('src') || '';
      const image = env.imageFor?.(src);
      return image ? `<img src="${escape(image)}" alt="${escape(token.content)}">` : escape(token.content || src);
    };
    // Only recorded references can turn a local Markdown destination into a file link.
    md.renderer.rules.link_open = (tokens, idx, options, env) => {
      const href = tokens[idx].attrGet('href') || '';
      let decoded = href;
      try { decoded = decodeURI(href); } catch { /* Keep malformed escapes inert. */ }
      const ref = (env.references || []).find(r => r.text === href || r.text === decoded);
      if (ref) return `<a class="ref" data-path="${escape(ref.path)}" data-kind="${ref.kind === 'dir' ? 'dir' : 'file'}" href="${escape(referenceHref(ref))}">`;
      if (/^https?:\/\//i.test(href)) return `<a href="${escape(href)}" target="_blank" rel="noopener noreferrer">`;
      return '<a>'; // Preserve label, without an unverified local navigation.
    };
    return md;
  }
  function segmentParts(segment, events) {
    const parts = [];
    for (const id of segment.ending_event_ids || []) {
      const event = events[id];
      if (!event) continue;
      let part = parts[parts.length - 1];
      if (!part || part.operation !== event.operation) { part = {operation:event.operation, files:[]}; parts.push(part); }
      if (event.ends_segment === 'write') { if (!part.files.some(f => f.path === event.path)) part.files.push({path:event.path, name:event.display_name}); }
      else if (event.display_name && !part.files.some(f => f.name === event.display_name)) part.files.push({path:event.path || null, name:event.display_name});
    }
    return parts;
  }
  function relatedWrittenFiles(data, event) {
    if (!event.tool_use_id) return [];
    return [...new Map(Object.values(data.events)
      .filter(e => e.kind !== 'group' && e.node_id === event.node_id && e.tool_use_id === event.tool_use_id)
      .flatMap(e => e.written_files || []).map(file => [file.path, file])).values()];
  }
  function buildTree(data) {
    const entries = new Map(), aliases = new Map(), emitted = new Set();
    const nodes = new Map(data.nodes.map(n => [n.id, n]));
    function entry(value, parent) {
      const result = {...value, parentId:parent?.id || null, children:[]};
      entries.set(result.id, result);
      if (parent) parent.children.push(result);
      return result;
    }
    function event(id, parent) {
      const e = data.events[id];
      if (!e) return;
      const kind = e.kind === 'group' || e.kind === 'inputs' ? e.kind : ['spawn', 'return', 'user'].includes(e.operation) ? e.operation : 'event';
      const row = entry({id, kind, event:e, path:e.path, output:!!e.is_output, expanded:e.operation === 'spawn'}, parent);
      for (const child of e.child_event_ids || []) event(child, row);
      if (e.child_node_id) agent(nodes.get(e.child_node_id), row);
    }
    function agent(node, parent) {
      if (!node || emitted.has(node.id)) return null;
      emitted.add(node.id);
      const row = entry({id:node.id, kind:'agent', node, expanded:true}, parent);
      const categories = node.initial_context?.categories || {};
      if (Object.keys(categories).length) {
        const initial = entry({id:node.id + '/initial', kind:'initial', node}, row);
        for (const [key, category] of Object.entries(categories)) {
          const categoryRow = entry({id:initial.id + '/' + key, kind:'category', node, category, categoryKey:key}, initial);
          for (const item of category.entries || []) entry({id:item.item_id, kind:'item', node, item:data.items[item.item_id], initialEntry:item, categoryKey:key, path:data.items[item.item_id]?.path}, categoryRow);
        }
      }
      // 段：两次写入文档之间的操作归到结尾那次写入下面；段里按时间排，新一轮开头画细线
      const requests = new Map((node.request_ids || []).map(rid => data.requests?.[rid]).filter(Boolean).map(r => [r.number, r]));
      const visible = ids => (ids || []).map(id => data.events[id]).filter(e => e && !['reply', 'think'].includes(e.operation)); // 模型说的话点开那一轮再看
      function fill(parent, events) {
        let last = null;
        for (let i = 0; i < events.length;) {
          const start = parent.children.length, number = events[i].request_number;
          let j = i;
          while (j < events.length && events[j].operation === 'read' && events[j].image_ids?.length && events[j].request_number === number) j++;
          if (j - i >= 3) { // 同一轮连续 3 张以上图片合成一行
            const run = events.slice(i, j), gid = `${parent.id}/images/${run[0].id}`;
            const group = entry({id:gid, kind:'group', expanded:false,
              event:{id:gid, kind:'group', operation:'read', display_name:`图片 ×${run.length}`, characters:0, child_event_ids:run.map(e => e.id), request_number:number}}, parent);
            for (const e of run) event(e.id, group);
            i = j;
          } else { event(events[i].id, parent); i++; }
          for (const child of parent.children.slice(start)) { child.round = number; child.request = requests.get(number); }
          if (last != null && number !== last && parent.children[start]) parent.children[start].roundStart = true;
          last = number;
        }
        foldCode(parent);
      }
      const segments = (node.segment_ids || []).map(id => data.segments?.[id]).filter(Boolean);
      if (!segments.some(s => s.end_kind !== 'open')) { fill(row, visible(node.event_ids)); return row; }
      fill(row, visible(node.leading_event_ids));
      // 只隔着模型说话、没有操作的两次写入并成一段
      const merged = [];
      for (const segment of segments) {
        const ops = visible(segment.event_ids), ends = visible(segment.ending_event_ids), prev = merged.at(-1);
        if (prev && !ops.length && segment.end_kind === 'write' && prev.segment.end_kind === 'write') {
          prev.ends.push(...ends); prev.range[1] = segment.request_range?.[1] ?? prev.range[1];
        } else merged.push({segment, ops, ends, range:[...(segment.request_range || [])]});
      }
      for (const {segment, ops, ends, range} of merged) {
        const spawn = segment.end_kind === 'spawn' && ends.length === 1 && ends[0].child_node_id ? ends[0] : null;
        const seg = entry({id:segment.id, kind:'segment', segment, expanded:!!spawn, ops:ops.length, ends, range}, row);
        if (spawn) { // 调用子 Agent 的那段：段这一行就是调用，子 Agent 直接挂在它下面
          fill(seg, ops); aliases.set(spawn.id, seg.id);
          agent(nodes.get(spawn.child_node_id), seg);
        } else fill(seg, [...ops, ...ends]);
      }
      return row;
    }
    // 连着两条以上的代码与命令合成一行
    function foldCode(parent) {
      const out = []; let run = [];
      const flush = () => {
        if (run.length >= 2) {
          const gid = `${parent.id}/code/${run[0].id}`;
          const group = {id:gid, kind:'group', fold:'code', parentId:parent.id, children:run, expanded:false, roundStart:run[0].roundStart,
            event:{id:gid, kind:'group', operation:'exec', display_name:`代码与命令 ×${run.length}`, characters:0, child_event_ids:run.map(c => c.event.id), request_number:run[0].round}};
          run[0].roundStart = false;
          for (const c of run) c.parentId = gid;
          entries.set(gid, group); out.push(group);
        } else out.push(...run);
        run = [];
      };
      for (const c of parent.children) { if (c.kind === 'event' && c.event?.is_code) run.push(c); else { flush(); out.push(c); } }
      flush(); parent.children = out;
    }
    const roots = [];
    for (const node of data.nodes.filter(n => !nodes.has(n.parent_id))) { const row = agent(node); if (row) roots.push(row); }
    for (const node of data.nodes) { const row = agent(node); if (row) roots.push(row); }
    return {roots, entries, aliases};
  }
  function expandAncestors(entries, id, expanded) {
    const seen = new Set();
    let row = entries.get(id);
    while (row?.parentId && !seen.has(row.parentId)) {
      seen.add(row.parentId); expanded.add(row.parentId); row = entries.get(row.parentId);
    }
    return [...seen];
  }
  function initViewer(doc, data, libraries) {
    const win = doc.defaultView;
    const $ = id => doc.getElementById(id);
    const model = buildTree(data), {entries, aliases} = model;
    const expanded = new Set([...entries.values()].filter(e => e.expanded).map(e => e.id));
    const rows = new Map(), branches = new Map(), nodes = new Map(data.nodes.map(n => [n.id, n]));
    const md = createMarkdown(libraries.markdownit);
    const scrollbars = new Map();
    let selected = '', sidePath = '', menuOrigin = null, graphObserver = null;
    const el = (tag, className, text) => {
      const element = doc.createElement(tag);
      if (className) element.className = className;
      if (text != null) element.textContent = text;
      return element;
    };
    const tagElement = operation => {
      const tag = actionTag(operation), element = el('span', 'tag', tag.text);
      element.style.setProperty('--tag-color', `var(${tag.color})`); return element;
    };
    const imageURL = id => {
      const image = data.images[id];
      return image && /^image\/(?:png|jpeg|jpg|gif|webp|avif|bmp)$/i.test(image.media_type || '') ? `data:${image.media_type};base64,${image.base64}` : null;
    };
    const shortPath = path => data.files[path]?.display_path || path;
    function fileLink(path, label) {
      const link = el('a', 'ref', label || shortPath(path));
      link.href = '#file'; link.dataset.path = path; link.title = path; return link;
    }
    function eventLink(id, label) {
      const event = data.events[id];
      const button = el('button', 'text-cell', label || join([`第 ${event?.request_number} 轮`, event?.operation_label, event?.display_name]));
      button.type = 'button'; button.dataset.target = id;
      if (event?.path) button.dataset.path = event.path;
      button.addEventListener('click', () => select(id, {locate:true})); return button;
    }
    function heading(target, text) { target.append(el('h2', '', text)); }
    function setHeading(text, meta = '', path = null) {
      $('editor-header').replaceChildren();
      const title = el('h1'); title.append(path ? fileLink(path, text) : doc.createTextNode(text));
      $('editor-header').append(title);
      if (meta) $('editor-header').append(el('p', 'crumb', meta));
    }
    function metadata(target, pairs) {
      const list = el('dl', 'meta card');
      for (const [key, value] of pairs) { list.append(el('dt', '', key)); const dd = el('dd'); dd.append(value?.nodeType ? value : doc.createTextNode(value ?? '未知')); list.append(dd); }
      target.append(list);
    }
    function table(target, labels, records, options = {}) {
      const table = el('table', 'data-table ' + (options.className || '')), thead = el('thead'), tr = el('tr');
      labels.forEach((label, index) => tr.append(el('th', options.numeric?.includes(index) ? 'numeric' : '', label)));
      thead.append(tr); table.append(thead); const tbody = el('tbody');
      for (const record of records) {
        const row = el('tr');
        record.forEach((value, index) => { const cell = el('td', options.numeric?.includes(index) ? 'numeric' : ''); cell.append(value?.nodeType ? value : doc.createTextNode(String(value ?? '—'))); row.append(cell); });
        tbody.append(row);
      }
      table.append(tbody); target.append(table); return table;
    }
    function source(target, value, options = {}) {
      if (value == null) return;
      const references = referenceCandidates(data, value, options);
      if (typeof value === 'string') {
        const markdown = shouldRenderMarkdown(options);
        const pane = el(markdown ? 'div' : 'pre', markdown ? 'markdown card' : 'source-pane');
        if (markdown) pane.innerHTML = md.render(value, {references, readRanges:options.readRanges || [], imageFor:src => {
          const ref = references.find(r => r.text === src);
          return ref ? (data.files[ref.path]?.image_ids || []).map(imageURL).find(Boolean) : null;
        }});
        else if (options.readRanges?.length) {
          const lines = value.split('\n');
          lines.forEach((line, index) => {
            const span = el('span', 'source-text-line', line + (index < lines.length - 1 ? '\n' : ''));
            span.dataset.lineStart = String(index + 1); span.dataset.lineEnd = String(index + 1);
            if (options.readRanges.some(r => r.start <= index + 1 && r.end >= index + 1)) span.classList.add('read-covered');
            pane.append(span);
          });
        } else pane.textContent = value;
        wrapReferences(pane, references); target.append(pane); return;
      }
      if (Array.isArray(value)) { for (const block of value) source(target, block, options); return; }
      if (typeof value !== 'object') { source(target, String(value), options); return; }
      if (value.type === 'image') {
        const src = value.source || {};
        if (src.type === 'base64' && /^image\/(?:png|jpeg|jpg|gif|webp|avif|bmp)$/i.test(src.media_type || '')) {
          const url = src.data_ref ? imageURL(src.data_ref) : src.data ? `data:${src.media_type};base64,${src.data}` : null;
          if (url) { const image = el('img', 'source-image'); image.src = url; image.alt = '图片'; target.append(image); }
        }
      } else if (value.type === 'tool_use') {
        heading(target, value.name || '工具调用'); parameters(target, value.input || {}, options);
      } else if (value.type === 'tool_result' || 'content' in value) source(target, value.content, options);
      else if (value.type === 'tool_addition') {
        for (const tool of value.tools || []) toolDefinition(target, tool, options);
      } else if ('input_schema' in value) toolDefinition(target, value, options);
      else if ('text' in value) source(target, value.text, options);
      else if (value.type === 'thinking') source(target, value.thinking, {...options, operation:'model'});
      else parameters(target, value, options);
    }
    function parameters(target, values, options) {
      for (const [key, value] of Object.entries(values || {})) {
        if (['role', 'type', 'id', 'tool_use_id', 'signature', 'usage'].includes(key)) continue;
        if (key !== 'command') heading(target, key);
        source(target, value, {...options, operation:'exec'});
      }
    }
    function toolDefinition(target, tool, options) {
      const box = el('section', 'tool-definition'); heading(box, tool.name || '工具');
      source(box, tool.description || '', {...options, operation:'tools'});
      const properties = tool.input_schema?.properties || tool.parameters?.properties || {};
      const required = new Set(tool.input_schema?.required || tool.parameters?.required || []);
      const typeOf = schema => Array.isArray(schema.type) ? schema.type.join(' / ') : schema.type || (schema.anyOf || schema.oneOf || []).map(typeOf).join(' / ') || (schema.enum ? 'enum' : '—');
      table(box, ['参数名', '类型', '说明'], Object.entries(properties).map(([name, schema]) => [name, typeOf(schema), join([schema.description || '', required.has(name) ? '必填' : ''])]));
      target.append(box);
    }
    function showImages(target, ids) {
      for (const id of ids || []) { const url = imageURL(id); if (!url) continue; const image = el('img', 'source-image'); image.src = url; image.alt = '读取的图片'; target.append(image); }
    }
    function eventProperties(event) {
      const range = event.read_range;
      return join([
        event.request_number != null ? `第 ${event.request_number} 轮` : '', event.operation_label, event.method,
        range ? range.kind === 'full' ? '全文读取' : `部分读取（${range.label || '范围未知'}）` : '',
        event.output_truncated ? `输出截断${event.truncation?.preview ? `（仅前 ${event.truncation.preview}）` : ''}` : '',
        event.failed ? '执行失败' : '',
        event.path ? ({same:'与当前文件一致', different:'与当前文件不一致', missing:'当前文件不存在'}[event.comparison_status] || '') : ''
      ]);
    }
    function contextOptions(event) {
      return {...event, sourcePath:event.path, ownerIds:[event.id, ...(event.item_ids || [])], nodeId:event.node_id};
    }
    function command(target, event) {
      const call = resolve(data, event.call_ref);
      if (call?.input) parameters(target, call.input, {...contextOptions(event), operation:'exec'});
    }
    function otherEvents(target, path, current) {
      const others = (data.files[path]?.event_ids || []).filter(id => id !== current);
      if (!others.length) return;
      heading(target, '文件的其他事件'); const links = el('div', 'entry-links');
      for (const id of others) links.append(eventLink(id)); target.append(links);
    }
    function showEvent(event, target = $('editor-content'), nested = false) {
      if (!event) return;
      if (!nested) setHeading(event.display_name || event.operation_label, eventProperties(event), event.path);
      const options = contextOptions(event);
      if (!nested && ['exec', 'list', 'fetch'].includes(event.operation)) {
        const written = relatedWrittenFiles(data, event);
        if (written.length) {
          const title = $('editor-header').querySelector('h1');
          title.append(doc.createTextNode(' · 写入 '));
          written.forEach((file, index) => {
            if (index) title.append(doc.createTextNode('、'));
            title.append(fileLink(file.path, basename(file.path)));
          });
        }
      }
      if (event.kind === 'group' || event.kind === 'inputs') {
        const links = el('div', 'entry-links');
        for (const id of event.child_event_ids || []) links.append(eventLink(id));
        target.append(links); return;
      }
      if (event.operation === 'spawn') {
        const siblings = nodes.get(event.node_id)?.event_ids || [];
        const before = siblings.indexOf(event.id);
        const user = siblings.slice(0, before).map(id => data.events[id]).reverse().find(e => e.operation === 'user');
        if (user) { heading(target, '用户消息'); source(target, resolve(data, user.content_ref), contextOptions(user)); }
        heading(target, '任务提示词'); source(target, resolve(data, event.content_ref), options);
      } else if (['write', 'edit'].includes(event.operation)) {
        showWrites(target, event.written_files || [], event);
        const segment = data.segments[event.segment_id];
        if (!nested && segment) showComposition(target, data.context_compositions[segment.context_composition_id]);
      } else {
        if (!['user', 'return', 'reminder', 'reply', 'think'].includes(event.operation)) command(target, event);
        showImages(target, event.image_ids);
        if (!event.image_ids?.length || contentText(resolve(data, event.content_ref)).trim()) source(target, resolve(data, event.content_ref), options);
      }
      if (event.path) otherEvents(target, event.path, event.id);
    }
    function showWrites(target, writes, fallbackEvent) {
      for (const write of writes) {
        const event = data.events[write.event_id] || fallbackEvent;
        const options = {...contextOptions(event), path:write.path, sourcePath:write.path, operation:event.operation};
        const title = el('h2'); title.append(fileLink(write.path), doc.createTextNode(` · 第 ${event.request_number} 轮`)); target.append(title);
        if (write.before_ref || write.after_ref) {
          if (write.before_ref) { heading(target, '改前'); source(target, resolve(data, write.before_ref), options); }
          if (write.after_ref) { heading(target, '改后'); source(target, resolve(data, write.after_ref), options); }
        } else if (write.content_ref) {
          if (write.content_kind === 'append') heading(target, '追加内容');
          source(target, resolve(data, write.content_ref), options);
        } else {
          command(target, event);
          target.append(el('p', 'empty', '记录中没有这次写入的内容。'));
        }
      }
    }
    function segmentTitle(segment) {
      return segmentParts(segment, data.events).map(part => actionTag(part.operation).text + (part.files.length ? ' ' + part.files.map(f => f.name).join('、') : '')).join('，') || '未结束分段';
    }
    function showSegment(segment) {
      const row = entries.get(segment.id), [a, b] = row?.range || segment.request_range || [];
      const endIds = row?.ends?.map(e => e.id) || segment.ending_event_ids || []; // 并过的段带上后面几次写入
      const events = endIds.map(id => data.events[id]).filter(Boolean);
      const meta = join([a == null ? '' : a === b ? `第 ${a} 轮` : `第 ${a}–${b} 轮`, `${num(row?.ops ?? segment.event_count)} 次操作`]);
      setHeading(segmentTitle({...segment, ending_event_ids:endIds}), meta, row?.path);
      const target = $('editor-content');
      if (segment.end_kind === 'write') {
        for (const event of events) {
          target.append(el('p', 'crumb', eventProperties(event)));
          showWrites(target, event.written_files || [], event);
        }
        showComposition(target, data.context_compositions[segment.context_composition_id]);
      } else if (events.length) for (const event of events) showEvent(event, target, true);
      else { const links = el('div', 'entry-links'); for (const id of segment.event_ids) links.append(eventLink(id)); target.append(links); }
    }
    function bar(target, categories) {
      const element = el('div', 'composition-bar'); element.setAttribute('role', 'img');
      element.setAttribute('aria-label', Object.values(categories).map(c => `${c.label} ${num(c.characters)} 字符`).join('；'));
      for (const [key, category] of Object.entries(categories)) {
        if (!category.characters) continue;
        const slice = el('span'); slice.style.flexGrow = category.characters;
        slice.style.setProperty('--category-color', `var(${CATEGORY_COLORS[key] || '--ink3'})`);
        slice.title = `${category.label} · ${num(category.characters)} 字符`; element.append(slice);
      }
      target.append(element);
    }
    function locatePart(part, composition) {
      const eventId = (part.event_ids || []).find(id => entries.has(id) || aliases.has(id));
      if (eventId) { select(eventId, {locate:true}); return; }
      if (entries.has(part.item_id)) { select(part.item_id, {locate:true}); return; }
      // Context without a tool event (e.g. model output) gets a source row only
      // on demand. It does not alter the initial chronological event counts.
      const parent = entries.get(composition.segment_id) || entries.get(composition.node_id);
      if (!parent) return;
      const id = `${composition.id}/source/${composition.categories ? Object.values(composition.categories).flatMap(c => c.parts || []).indexOf(part) : part.item_id}`;
      if (!entries.has(id)) {
        const item = data.items[part.item_id];
        const entry = {id, parentId:parent.id, kind:'context', item, rawRef:part.raw_ref, node:nodes.get(composition.node_id), children:[]};
        entries.set(id, entry); parent.children.push(entry); renderTree();
      }
      select(id, {locate:true});
    }
    function showComposition(target, composition) {
      if (!composition) return;
      const request = data.requests[composition.request_id];
      heading(target, `第 ${request?.number ?? composition.request_id.split('/').pop()} 轮 · 上下文构成`);
      const box = el('section', 'context-composition'); box.dataset.requestId = composition.request_id;
      bar(box, composition.categories);
      const records = Object.entries(composition.categories).map(([key, category]) => {
        const cell = el('div'), dot = el('span', 'category-dot'); dot.style.setProperty('--category-color', `var(${CATEGORY_COLORS[key]})`);
        const button = el('button', 'text-cell'); button.append(dot, doc.createTextNode(category.label));
        const parts = category.parts || [];
        button.addEventListener('click', () => { if (parts[0]) locatePart(parts[0], composition); }); cell.append(button);
        if (parts.length) {
          const details = el('details', 'content-entry'), list = el('div', 'composition-parts');
          details.append(el('summary', 'secondary', `${num(parts.length)} 项`));
          for (const part of parts) {
            const item = data.items[part.item_id];
            const entry = el('button'); entry.type = 'button'; entry.dataset.itemId = part.item_id;
            if (part.event_ids?.length) entry.dataset.target = part.event_ids[0];
            entry.append(el('span', '', item?.label || '上下文内容'), el('span', 'secondary num', num(part.characters)));
            if (item?.path) entry.dataset.path = item.path;
            entry.addEventListener('click', () => locatePart(part, composition)); list.append(entry);
          }
          details.append(list); cell.append(details);
        }
        return [cell, num(category.characters)];
      });
      const element = table(box, ['类别 / 内容', '字符数'], records, {numeric:[1], className:'composition-table'});
      const foot = el('tfoot'), row = el('tr'); row.append(el('td', '', '合计'), el('td', 'numeric', num(composition.characters))); foot.append(row); element.append(foot);
      target.append(box);
    }
    function showInitial(node, onlyCategory) {
      const initial = node.initial_context, target = $('editor-content');
      setHeading(onlyCategory ? initial.categories[onlyCategory].label : '上下文', `${node.title} · 第 ${data.requests[initial.request_id]?.number ?? 1} 轮`);
      const categories = onlyCategory ? {[onlyCategory]:initial.categories[onlyCategory]} : initial.categories;
      bar(target, categories);
      table(target, ['类别', '字符数'], Object.entries(categories).map(([key, category]) => {
        const button = el('button', 'text-cell', category.label);
        button.addEventListener('click', () => select(node.id + '/initial/' + key, {locate:true}));
        return [button, num(category.characters)];
      }), {numeric:[1]});
      for (const [key, category] of Object.entries(categories)) {
        heading(target, `${category.label} · ${(category.entries || []).length} 项`);
        for (const entry of category.entries || []) {
          const item = data.items[entry.item_id], details = el('details', 'content-entry card');
          details.dataset.itemId = entry.item_id;
          const summary = el('summary', '', join([entry.name || item?.label || category.label, `${num(entry.characters)} 字符`, entry.available_in_first_request === false ? `第 ${entry.first_request} 轮加入` : '']));
          if (item?.path) summary.dataset.path = item.path;
          details.append(summary);
          const render = () => {
            if (details.dataset.rendered) return;
            details.dataset.rendered = 'true';
            showItemContent(details, {...entry, item, categoryKey:key, node});
          };
          details.addEventListener('toggle', () => { if (details.open) render(); });
          if (onlyCategory === key && key === 'tools') { details.open = true; render(); }
          target.append(details);
        }
      }
    }
    function showItemContent(target, entry) {
      const item = entry.item || {}, ref = entry.rawRef || entry.content_ref || entry.initialEntry?.content_ref || item.display_ref;
      const refs = entry.content_refs || entry.initialEntry?.content_refs;
      const options = {ownerIds:[item.id], sourcePath:item.path, nodeId:item.node_id || entry.node?.id, path:item.path,
        operation:entry.categoryKey === 'task' ? 'task' : item.path ? 'read' : entry.categoryKey || 'model', read_range:{kind:'full'}};
      if (refs) for (const part of refs) source(target, resolve(data, part), options);
      else if (entry.categoryKey === 'tools') toolDefinition(target, resolve(data, ref) || {}, options);
      else if (ref) source(target, resolve(data, ref), options);
      else for (const fragment of item.fragments || []) source(target, resolve(data, fragment.raw_ref || fragment.ref), options);
    }
    function roundInfo(target, node, number) {
      const requests = (node.request_ids || []).map(rid => data.requests[rid]).filter(Boolean).sort((a, b) => a.number - b.number);
      const index = requests.findIndex(r => r.number === number), request = requests[index];
      if (!request) return;
      const next = requests[index + 1];
      const start = Date.parse(request.timestamp), end = next?.timestamp ? Date.parse(next.timestamp) : node.end ? Date.parse(node.end) : NaN;
      const seconds = Math.round((end - start) / 1000);
      heading(target, `第 ${number} 轮`);
      metadata(target, [['模型', request.params?.model || '未知'], ['时间', request.timestamp_bjt?.slice(11, 19) || '未知'],
        ['耗时', Number.isFinite(seconds) ? (seconds < 90 ? seconds + 's' : (seconds / 60).toFixed(1) + 'min') : '未知'],
        ['上下文 tokens', num(request.context_tokens)]]);
      const replies = (node.event_ids || []).map(id => data.events[id]).filter(e => e && e.request_number === number && ['reply', 'think'].includes(e.operation));
      if (replies.length) { heading(target, '模型这一轮说的话'); for (const e of replies) source(target, resolve(data, e.content_ref), contextOptions(e)); }
    }
    function showAgent(node) {
      const overview = node.overview, target = $('editor-content');
      setHeading(node.agent_id ? `子 Agent ${node.title}` : '主 Agent');
      metadata(target, [['轮数', num(overview.request_count)], ['时间', dateRange(node.start_bjt, node.end_bjt)],
        ['上下文 tokens', `${num(overview.context_tokens.first)} → ${num(overview.context_tokens.last)}`]]);
      heading(target, '操作类型');
      table(target, ['操作', '事件数'], Object.entries(overview.operation_counts).filter(([, count]) => count).map(([operation, count]) => [tagElement(operation), num(count)]), {numeric:[1]});
      heading(target, '读取的文件');
      table(target, ['路径', '次数', '首次出现', '字符数'], overview.read_files.map(file => [fileLink(file.path), num(file.count), `第 ${file.first_request} 轮`, num(file.characters)]), {numeric:[1,2,3]});
      heading(target, '写入的文件');
      table(target, ['路径', '次数'], overview.written_files.map(file => [fileLink(file.path), num(file.count)]), {numeric:[1]});
      if (overview.focus_coverage) {
        heading(target, '焦点文件覆盖');
        table(target, ['路径', '链路事件数'], overview.focus_coverage.map(file => [fileLink(file.path), num(file.event_ids.length)]), {numeric:[1]});
      }
    }
    function showTrace() {
      setHeading('追踪总览', dateRange(data.scope.start_bjt, data.scope.end_bjt));
      const graph = el('div', 'flow'); graph.setAttribute('aria-label', 'Agent 调用与文件流转');
      const layout = traceGraph(data), buttons = new Map(), routes = [];
      graph.style.setProperty('--node-count', Math.max(1, layout.nodes.length));
      const svgElement = (tag, attributes = {}) => {
        const element = doc.createElementNS('http://www.w3.org/2000/svg', tag);
        for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
        return element;
      };
      const svg = svgElement('svg', {class:'flow-lines', 'aria-hidden':'true'});
      const defs = svgElement('defs'), marker = svgElement('marker', {id:'flow-arrow', viewBox:'0 0 10 10', refX:'9', refY:'5', markerWidth:'6', markerHeight:'6', orient:'auto-start-reverse'});
      marker.append(svgElement('path', {d:'M 0 0 L 10 5 L 0 10 z', fill:'var(--accent)'})); defs.append(marker); svg.append(defs); graph.append(svg);
      layout.nodes.forEach((node, index) => {
        const button = el('button', 'flow-node', node.agent_id ? node.title : '主 Agent');
        button.dataset.nodeId = node.id; button.style.gridColumn = index + 1; button.style.gridRow = 1;
        button.addEventListener('click', () => select(node.id, {locate:true}));
        buttons.set(node.id, button); graph.append(button);
      });
      for (const [index, edge] of layout.edges.entries()) {
        const from = layout.nodes.findIndex(node => node.id === edge.source_node_id), to = layout.nodes.findIndex(node => node.id === edge.target_node_id);
        const row = el('div', 'flow-edge'); row.dataset.kind = edge.kind; row.dataset.edgeId = edge.id;
        row.style.gridColumn = `${Math.min(from, to) + 1} / ${Math.max(from, to) + 2}`; row.style.gridRow = index + 2;
        const route = el('div', 'flow-route');
        if (edge.kind === 'file_flow') {
          const sourceNumber = data.events[edge.source_event_id]?.request_number ?? edge.version_request_id?.split('/').pop();
          const targetNumber = data.events[edge.target_event_id]?.request_number ?? edge.read_request_id?.split('/').pop();
          route.append(fileLink(edge.path, basename(edge.path)), doc.createTextNode('：'));
          route.append(edge.source_event_id ? eventLink(edge.source_event_id, `第 ${sourceNumber} 轮写入`) : doc.createTextNode(`第 ${sourceNumber} 轮写入`));
          route.append(doc.createTextNode(' → '));
          route.append(edge.target_event_id ? eventLink(edge.target_event_id, `第 ${targetNumber} 轮读取`) : doc.createTextNode(`第 ${targetNumber} 轮读取`));
        } else route.append(edge.source_event_id ? eventLink(edge.source_event_id, '调用') : doc.createTextNode('调用'));
        row.append(route); graph.append(row);
        const path = svgElement('path', {class:'flow-line', 'data-kind':edge.kind, 'marker-end':'url(#flow-arrow)'}); svg.append(path);
        routes.push({edge, row, path});
      }
      $('editor-content').append(graph);
      const draw = () => {
        if (!graph.isConnected) return;
        const bounds = graph.getBoundingClientRect();
        for (const {edge, row, path} of routes) {
          const a = buttons.get(edge.source_node_id).getBoundingClientRect(), b = buttons.get(edge.target_node_id).getBoundingClientRect(), lane = row.getBoundingClientRect();
          const x1 = a.left + a.width / 2 - bounds.left, x2 = b.left + b.width / 2 - bounds.left, y = lane.top + lane.height / 2 - bounds.top;
          path.setAttribute('d', `M ${x1} ${a.bottom - bounds.top} V ${y} H ${x2} V ${b.bottom - bounds.top + 2}`);
        }
      };
      win.requestAnimationFrame(draw);
      if (win.ResizeObserver) { graphObserver = new win.ResizeObserver(draw); graphObserver.observe(graph); }
    }
    function termLabel(text, className = 'tree-label') { return el('span', className, text); }
    function rowContent(entry, row) {
      if (entry.kind === 'agent') {
        const label = el('span', 'tree-label');
        label.append(termLabel(entry.node.agent_id ? '子 Agent' : '主 Agent', ''));
        if (entry.node.agent_id) label.append(doc.createTextNode(' ' + entry.node.title));
        row.append(label); return;
      }
      if (entry.kind === 'initial') { row.append(termLabel('上下文')); return; }
      if (entry.kind === 'category') { row.append(termLabel(entry.category?.label || '')); return; }
      if (entry.kind === 'segment') {
        if (entry.ops || !entry.ends.length) row.append(el('span', 'seg-ops', entry.ends.length ? `${entry.ops} 次操作 →` : `${entry.ops} 次操作`));
        // 同一种操作只写一次标签：写入 a.md、b.md；同一个文件只写一次
        const seen = new Set();
        let lastOperation = null, names = null;
        for (const e of entry.ends) {
          if (seen.has(e.path || e.id)) continue;
          seen.add(e.path || e.id);
          if (e.operation !== lastOperation) {
            if (lastOperation) row.append(el('span', 'seg-sep', '，'));
            const tag = tagElement(e.operation); row.append(tag);
            names = el('span', 'tree-label'); row.append(names); lastOperation = e.operation;
          } else names.append(doc.createTextNode('、'));
          const name = shortName(e, data);
          if (name && name !== actionTag(e.operation).text) names.append(el('span', isUserFile(e.path) ? 'name-hl' : '', name));
        }
        const chars = entry.ends.reduce((sum, e) => sum + (e.characters || 0), 0);
        if (chars) row.append(el('span', 'tree-count', num(chars)));
        return;
      }
      if (entry.kind === 'item') {
        const name = el('span', 'tree-label' + (isUserFile(entry.path) ? ' name-hl' : ''), entry.initialEntry?.name || entry.item?.label || '上下文内容');
        row.append(name);
        const count = entry.initialEntry?.characters ?? entry.item?.characters;
        if (count > 0) row.append(el('span', 'tree-count', num(count)));
        return;
      }
      const event = entry.event;
      if (!event) { row.append(el('span', 'tree-label', '上下文内容')); return; }
      if (entry.roundStart) row.classList.add('round-start');
      if (entry.fold === 'code') { row.classList.add('code-fold'); row.append(el('span', 'tree-label', event.display_name)); return; }
      row.append(tagElement(event.operation));
      const name = event.kind === 'group' ? event.display_name : shortName(event, data);
      row.append(el('span', 'tree-label' + (isUserFile(event.path) ? ' name-hl' : ''), name));
      if (eventCharacterCount(event)) row.append(el('span', 'tree-count', eventCharacterCount(event)));
    }
    function renderTree() {
      $('tree').replaceChildren(); rows.clear(); branches.clear();
      function render(entry, parent, depth) {
        const wrapper = el('div', 'tree-entry'), row = el('div', `tree-row kind-${entry.kind}`);
        row.dataset.kind = entry.kind; row.dataset.id = entry.id;
        if (entry.path) row.dataset.path = entry.path; // 11-04 用户：侧栏悬停不弹任何内容
        row.style.setProperty('--indent', `${6 + depth * 12}px`);
        row.setAttribute('role', 'treeitem'); row.setAttribute('aria-level', String(depth + 1));
        row.setAttribute('aria-selected', String(selected === entry.id)); row.tabIndex = selected === entry.id ? 0 : -1;
        const twisty = el('span', 'twisty' + (entry.children.length ? '' : ' empty')); twisty.setAttribute('aria-hidden', 'true'); row.append(twisty);
        rowContent(entry, row); wrapper.append(row); rows.set(entry.id, row);
        if (entry.children.length) {
          const children = el('div', 'tree-children'); children.setAttribute('role', 'group');
          children.style.setProperty('--guide-left', `${11 + depth * 12}px`);
          children.hidden = !expanded.has(entry.id); row.setAttribute('aria-expanded', String(!children.hidden)); branches.set(entry.id, children);
          for (const child of entry.children) render(child, children, depth + 1);
          wrapper.append(children);
        }
        row.addEventListener('click', () => {
          if (entry.children.length) toggle(entry.id);
          select(entry.id);
        });
        parent.append(wrapper);
      }
      for (const root of model.roots) render(root, $('tree'), 0);
      if (sidePath) markFile(sidePath, false);
    }
    function toggle(id, force) {
      const branch = branches.get(id);
      if (!branch) return;
      const open = force == null ? !expanded.has(id) : force;
      if (open) expanded.add(id); else expanded.delete(id);
      branch.hidden = !open; rows.get(id).setAttribute('aria-expanded', String(open));
    }
    function revealRow(id, scroll = true) {
      id = aliases.get(id) || id;
      for (const ancestor of expandAncestors(entries, id, expanded)) toggle(ancestor, true);
      if (scroll) rows.get(id)?.scrollIntoView({block:'nearest', inline:'nearest'});
      return id;
    }
    function viewport(id) { return scrollbars.get(id)?.elements().viewport || $(id); }
    function select(id, options = {}) {
      const rowId = aliases.get(id) || id, entry = entries.get(rowId);
      if (!entry && id !== 'trace') return;
      graphObserver?.disconnect(); graphObserver = null;
      selected = rowId;
      for (const [key, row] of rows) { row.setAttribute('aria-selected', String(key === rowId)); row.tabIndex = key === rowId ? 0 : -1; }
      $('editor-content').replaceChildren();
      if (id === 'trace') showTrace();
      else if (data.events[id] && aliases.has(id)) showEvent(data.events[id]);
      else if (entry.kind === 'agent') showAgent(entry.node);
      else if (entry.kind === 'initial' || entry.kind === 'category') showInitial(entry.node, entry.categoryKey);
      else if (entry.segment) showSegment(entry.segment);
      else if (entry.event) { showEvent(entry.event); const node = nodes.get(entry.event.node_id) || nodes.get(entry.parentId); if (node && entry.round != null) roundInfo($('editor-content'), node, entry.round); }
      else { setHeading(entry.initialEntry?.name || entry.item?.label || '上下文内容'); showItemContent($('editor-content'), entry); }
      viewport('editor-body').scrollTop = 0;
      if (options.locate) revealRow(rowId);
      for (const scrollbar of scrollbars.values()) scrollbar.update();
    }
    function clearLocated() { for (const row of rows.values()) row.classList.remove('located'); }
    function markFile(path, scroll = true) {
      clearLocated();
      const ids = [...new Set((data.files[path]?.event_ids || []).map(id => aliases.get(id) || id))];
      for (const id of ids) { revealRow(id, false); rows.get(id)?.classList.add('located'); }
      if (scroll && ids.length) rows.get(ids[0])?.scrollIntoView({block:'nearest', inline:'nearest'});
    }
    function openFile(path) {
      const file = data.files[path];
      if (!file) return;
      sidePath = path; $('side-pane').hidden = false; $('side-splitter').hidden = false; $('workbench').classList.add('with-side');
      const target = $('side-content'); target.replaceChildren();
      const title = el('h1'); title.append(fileLink(path, path)); target.append(title);
      target.append(el('p', 'crumb', `在链路中出现 ${file.event_ids.length} 次`));
      if (file.content_version === 'last_read') target.append(el('p', 'crumb version-note', `运行后文件已变更，显示第 ${file.last_read_request_number} 轮读取到的内容`));
      const links = el('div', 'entry-links'); for (const id of file.event_ids) links.append(eventLink(id)); target.append(links);
      const last = data.events[file.last_read_event_id];
      if (file.type === 'image') showImages(target, file.image_ids);
      else if (file.content_ref) source(target, resolve(data, file.content_ref), {
        ...(file.content_version === 'last_read' && last ? contextOptions(last) : {}),
        path, sourcePath:path, ownerIds:file.event_ids, version:file.content_version,
        operation:file.content_version === 'last_read' ? last?.operation || 'read' : 'read',
        readRanges:[] // 11-04 用户：读取范围不在侧栏标注
      });
      else target.append(el('p', 'empty', ({over_1mb:'文件超过 1 MiB，未嵌入全文。', missing:'当前文件不存在。', no_recorded_read:'记录中没有可显示的读取内容。', not_text:'文件不是文本。', not_utf8_or_unreadable:'文件无法作为 UTF-8 文本读取。'}[file.omitted_reason] || '记录中没有可显示的文件内容。')));
      for (const scrollbar of scrollbars.values()) scrollbar.update(true);
      viewport('side-body').scrollTop = 0; markFile(path);
    }
    function closeFile() {
      sidePath = ''; clearLocated(); $('side-pane').hidden = true; $('side-splitter').hidden = true; $('workbench').classList.remove('with-side');
      for (const scrollbar of scrollbars.values()) scrollbar.update(true);
    }
    function closeMenu(restoreFocus = false) {
      $('context-menu').hidden = true;
      if (restoreFocus) menuOrigin?.focus();
    }
    async function copyPath(path) {
      try { await win.navigator.clipboard.writeText(path); }
      catch {
        const input = el('textarea'); input.value = path; input.setAttribute('readonly', '');
        input.style.position = 'fixed'; input.style.opacity = '0'; doc.body.append(input); input.select(); doc.execCommand('copy'); input.remove();
      }
    }
    function showMenu(path, x, y, origin) {
      const menu = $('context-menu'); menu.replaceChildren(); menuOrigin = origin;
      for (const action of fileMenuActions(path)) {
        const link = el('a', '', action.label); link.href = action.href; link.dataset.action = action.id; link.setAttribute('role', 'menuitem');
        link.addEventListener('click', event => {
          if (action.id === 'copy') { event.preventDefault(); void copyPath(action.path); }
          closeMenu();
        }); menu.append(link);
      }
      menu.hidden = false;
      menu.style.left = `${Math.max(8, Math.min(x, win.innerWidth - menu.offsetWidth - 8))}px`;
      menu.style.top = `${Math.max(8, Math.min(y, win.innerHeight - menu.offsetHeight - 8))}px`;
      menu.querySelector('a')?.focus();
    }
    // Capture Command clicks before row / reference handlers change selection.
    const referenceActions = {navigate:href => { win.location.href = href; }, openFile};
    doc.addEventListener('click', event => {
      const file = event.target.closest('[data-path]');
      if (event.metaKey && file && absolutePath(file.dataset.path)) {
        event.preventDefault(); event.stopImmediatePropagation();
        activateReference(file.dataset, referenceActions, true); return;
      }
      const ref = event.target.closest('a.ref[data-path]');
      if (ref) { event.preventDefault(); event.stopImmediatePropagation(); closeMenu(); activateReference(ref.dataset, referenceActions); return; }
      if (!event.target.closest('#context-menu')) closeMenu();
    }, true);
    doc.addEventListener('contextmenu', event => {
      const file = event.target.closest('[data-path]');
      if (!file || !absolutePath(file.dataset.path)) return;
      event.preventDefault(); showMenu(file.dataset.path, event.clientX, event.clientY, file);
    });
    doc.addEventListener('keydown', event => {
      if (event.key === 'Escape') { closeMenu(true); return; }
      if (!$('context-menu').hidden && ['ArrowDown', 'ArrowUp'].includes(event.key)) {
        event.preventDefault(); const links = [...$('context-menu').querySelectorAll('a')];
        const next = (links.indexOf(doc.activeElement) + (event.key === 'ArrowDown' ? 1 : -1) + links.length) % links.length; links[next]?.focus();
      }
    });
    $('tree').addEventListener('keydown', event => {
      const row = event.target.closest('.tree-row'); if (!row) return;
      const entry = entries.get(row.dataset.id);
      const visible = [...rows.values()].filter(r => !r.closest('[hidden]'));
      let focus;
      if (event.key === 'ArrowDown') focus = visible[visible.indexOf(row) + 1];
      else if (event.key === 'ArrowUp') focus = visible[visible.indexOf(row) - 1];
      else if (event.key === 'ArrowRight') { toggle(entry.id, true); focus = rows.get(entry.children[0]?.id); }
      else if (event.key === 'ArrowLeft') { if (expanded.has(entry.id)) toggle(entry.id, false); else focus = rows.get(entry.parentId); }
      else if (['Enter', ' '].includes(event.key)) row.click();
      else return;
      event.preventDefault(); focus?.focus();
    });
    function splitter(id, property, side) {
      const handle = $(id);
      const set = width => {
        const limit = $('workbench').clientWidth * (side ? .50 : .65);
        const next = Math.min(Math.max(160, width), limit);
        doc.documentElement.style.setProperty(property, `${next}px`); handle.setAttribute('aria-valuenow', String(Math.round(next)));
        for (const scrollbar of scrollbars.values()) scrollbar.update();
      };
      handle.setAttribute('aria-valuemin', '160');
      handle.addEventListener('pointerdown', event => {
        if (event.button !== 0) return;
        event.preventDefault(); const start = event.clientX, width = $(side ? 'side-pane' : 'sidebar').getBoundingClientRect().width;
        handle.setPointerCapture(event.pointerId); doc.body.classList.add('resizing');
        const move = e => set(width + (e.clientX - start) * (side ? -1 : 1));
        const done = () => { doc.body.classList.remove('resizing'); handle.removeEventListener('pointermove', move); handle.removeEventListener('pointerup', done); handle.removeEventListener('pointercancel', done); };
        handle.addEventListener('pointermove', move); handle.addEventListener('pointerup', done); handle.addEventListener('pointercancel', done);
      });
      handle.addEventListener('keydown', event => {
        if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
        event.preventDefault(); set($(side ? 'side-pane' : 'sidebar').getBoundingClientRect().width + (event.key === 'ArrowRight' ? 20 : -20) * (side ? -1 : 1));
      });
    }
    function dateRange(start, end) {
      if (!start) return '';
      const format = text => text ? `${text.slice(5,10)} ${text.slice(11,16)}` : '未知';
      return `${format(start)}–${start.slice(0,10) === end?.slice(0,10) ? end.slice(11,16) : format(end)}`;
    }
    const directory = data.scope.from_output?.split('/').slice(0, -1).slice(-2).join(' / ');
    $('scope').textContent = directory || '追踪'; doc.title = `${directory || '追踪'} · agent-context-trace`;
    $('scope-time').textContent = dateRange(data.scope.start_bjt, data.scope.end_bjt);
    for (const node of data.nodes.filter(isSegmented)) {
      const overview = node.overview, line = el('div', 'role');
      line.append(el('b', '', node.agent_id ? node.title : '主 Agent'), doc.createTextNode(' · 读取 '), el('span', 'num', num(overview.read_files.reduce((sum, f) => sum + f.characters, 0))),
        doc.createTextNode(' 字符 · 上下文 tokens '), el('span', 'num', num(overview.context_tokens.first)), doc.createTextNode(' → '), el('span', 'num', num(overview.context_tokens.last)));
      $('node-overview').append(line);
    }
    const glossary = $('glossary');
    if (glossary) for (const [term, meaning] of GLOSSARY) glossary.append(el('dt', '', term), el('dd', '', meaning));
    $('scope').addEventListener('click', () => select('trace')); $('side-close').addEventListener('click', closeFile);
    renderTree();
    splitter('splitter', '--sidebar-width', false); splitter('side-splitter', '--side-width', true);
    if (libraries.OverlayScrollbars) for (const id of ['tree-scroll', 'editor-body', 'side-body']) {
      // Keep the documented DOM IDs on the actual scrollable viewports.
      scrollbars.set(id, libraries.OverlayScrollbars({target:$(id).parentElement, elements:{viewport:$(id)}},
        {overflow:{x:id === 'tree-scroll' ? 'scroll' : 'hidden', y:'scroll'}, scrollbars:{autoHide:'scroll', autoHideDelay:600, theme:'os-theme-dark'}}));
    }
    select(data.nodes.find(n => n.agent_id)?.id || data.nodes[0]?.id || 'trace');
    doc.documentElement.dataset.ready = 'true';
    return {select, openFile, closeFile, model};
  }
  const api = {ACTION_TAGS, GLOSSARY, isUserFile, shortName, actionTag, resolve, contentText, shouldRenderMarkdown, fileMenuActions, referenceHref, activateReference, referenceCandidates, referenceMatches, wrapReferences, createMarkdown, segmentParts, relatedWrittenFiles, isSegmented, eventCharacterCount, traceGraph, buildTree, expandAncestors, initViewer};
  if (typeof module === 'object' && module.exports) { module.exports = api; return; }
  initViewer(document, JSON.parse(document.getElementById('trace-data').textContent), {markdownit:window.markdownit, OverlayScrollbars:window.OverlayScrollbarsGlobal.OverlayScrollbars});
})();
