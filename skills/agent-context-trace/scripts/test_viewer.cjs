// Synthetic presentation regressions. No trace excerpts and no npm dependencies.
const assert = require('node:assert/strict');
const test = require('node:test');
const markdownit = require('../assets/vendor/markdown-it.min.js');
const viewer = require('../assets/viewer.js');
const {ACTION_TAGS, actionTag, shouldRenderMarkdown, fileMenuActions, referenceCandidates,
  referenceMatches, wrapReferences, createMarkdown, segmentParts, buildTree, expandAncestors} = viewer;

test('all operation labels use only the specified existing palette tokens', () => {
  const expected = {
    read:['读取','--t-read'], search:['查找','--t-read'], filter:['过滤','--t-read'], list:['列出','--t-read'],
    write:['写入','--t-write'], edit:['编辑','--t-write'], exec:['执行','--t-run'], fetch:['抓取','--t-run'],
    spawn:['调用','--t-task'], return:['返回','--t-task'], user:['用户','--t-task'], reminder:['提醒','--t-auto'],
    reply:['回复','--t-img'], think:['思考','--t-img'], inputs:['输入','--ink2']
  };
  assert.deepEqual(Object.keys(ACTION_TAGS), Object.keys(expected));
  for (const [key, [text, color]] of Object.entries(expected)) assert.deepEqual(actionTag(key), {text, color});
  assert.deepEqual(actionTag({operation:'read', image_ids:['image']}), ACTION_TAGS.read);
});

test('scalar tool parameters are safe to inspect and do not invent reference text', () => {
  for (const value of [180000, 0, true, false, null, undefined]) {
    assert.equal(viewer.contentText(value), '');
    assert.deepEqual(referenceCandidates({sources:{},file_references:[]}, value), []);
  }
  assert.equal(viewer.contentText({role:'user',content:[{type:'text',text:'hello'}, {type:'text',text:' world'}]}), 'hello world');
});

test('Markdown is limited to continuous Markdown sources and message prose', () => {
  const full = {operation:'read', path:'/demo/file.md', read_range:{kind:'full'}};
  assert.equal(shouldRenderMarkdown(full), true);
  for (const method of ['Read','head','tail']) assert.equal(shouldRenderMarkdown({...full, read_range:{kind:'partial', selectors:[{method, lines:4}]}}), true);
  assert.equal(shouldRenderMarkdown({...full, read_range:{kind:'partial', selectors:[{method:'sed',ranges:[[2,5]]}]}}), true);
  for (const operation of ['user','task','spawn','return']) assert.equal(shouldRenderMarkdown({operation}), true);
  for (const operation of ['write','edit']) assert.equal(shouldRenderMarkdown({operation,path:'/demo/file.md'}), true);
  assert.equal(shouldRenderMarkdown({path:'/demo/file.md',version:'current'}), true);
  for (const override of [
    {operation:'search'}, {operation:'filter'}, {operation:'exec'}, {operation:'list'}, {operation:'fetch'},
    {operation:'reminder'}, {output_truncated:true}, {failed:true}, {shared_with:['/demo/other.md']}, {path:'/demo/file.py'},
    {read_range:{kind:'partial',selectors:[{method:'head',bytes:20}]}},
    {read_range:{kind:'partial',selectors:[{method:'sed',ranges:[[2,3],[8,9]]}]}},
    {read_range:{kind:'partial',selectors:[{method:'awk'}]}},
    {read_range:{kind:'partial',selectors:[]}}
  ]) assert.equal(shouldRenderMarkdown({...full,...override}), false, JSON.stringify(override));
});

test('Markdown renders lists/tables/code, keeps HTML inert and never requests remote images', () => {
  const md = createMarkdown(markdownit);
  assert.equal(md.options.html, false);
  const html = md.render('# Header\n\n- item\n\n| A | B |\n|---|---|\n|x|y|\n\n```js\na < b\n```\n\n<img src="https://invalid.test/a">\n\n![alt](https://invalid.test/b)\n');
  for (const tag of ['h1','ul','table','pre','code']) assert.match(html, new RegExp('<'+tag+'[ >]'));
  assert.match(html, /a &lt; b/);
  assert.match(html, /&lt;img/);
  assert.doesNotMatch(html, /<img/);
  assert.doesNotMatch(html, /line-number/);
  assert.doesNotThrow(() => md.render('[bad](file%xx.md)'));
});

test('Markdown block maps highlight only source blocks intersecting recorded read ranges', () => {
  const md = createMarkdown(markdownit);
  const html = md.render('# Title\n\nparagraph\n\n```js\nvalue\n```\n', {readRanges:[{start:3,end:3},{start:6,end:6}]});
  assert.match(html, /<h1 data-line-start="1" data-line-end="1">/);
  assert.match(html, /<p data-line-start="3" data-line-end="3" class="read-covered">/);
  assert.match(html, /<pre data-line-start="5" data-line-end="7" class="read-covered">/);
  assert.doesNotMatch(html, /<h1[^>]*read-covered/);
});

test('references use Unicode code points and stay scoped to their source owner', () => {
  const text = '😀 Read `references/a.md` and a.md.';
  const start = Array.from(text).join('').indexOf('references/') - 1;
  const data = {sources:{s:text},file_references:[
    {text_ref:{source_id:'s'},start,end:start+15,path:'/one/a.md',node_id:'a',source_path:'/one/SKILL.md',owner_ids:['ea']},
    {text_ref:{source_id:'s'},start,end:start+15,path:'/two/a.md',node_id:'b',source_path:'/two/SKILL.md',owner_ids:['eb']}
  ]};
  assert.deepEqual(referenceCandidates(data,text,{ownerIds:['ea'],nodeId:'a',sourcePath:'/one/SKILL.md'}),[{text:'references/a.md',path:'/one/a.md',kind:'file'}]);
  assert.deepEqual(referenceCandidates(data,text,{ownerIds:['ea','eb']}),[]);
  assert.deepEqual(referenceCandidates(data,text,{ownerIds:['missing']}),[]);
});

test('reference matching prefers the full path, repeats links, and ignores Markdown offsets', () => {
  const matches = referenceMatches('prefix references/a.md plus a.md references/a.md', [
    {text:'a.md',path:'/short/a.md'}, {text:'references/a.md',path:'/long/a.md'}
  ]);
  assert.deepEqual(matches.map(m => m.path), ['/long/a.md','/short/a.md','/long/a.md']);
});

// Small DOM fixture for the standard text-node APIs used by wrapReferences.
class Node {
  constructor(tag, doc, value) { this.tagName=tag?.toUpperCase(); this.ownerDocument=doc; this.nodeValue=value; this.children=[]; this.dataset={}; }
  get parentElement() { return this.parent; }
  append(...nodes) { for (const node of nodes) { if(node.tagName==='#FRAGMENT') this.append(...node.children); else { this.children.push(node); node.parent=this; } } }
  closest(selectors) { return selectors.split(',').includes(this.tagName?.toLowerCase()) ? this : this.parent?.closest(selectors); }
  replaceWith(fragment) { const p=this.parent, i=p.children.indexOf(this); p.children.splice(i,1,...fragment.children); fragment.children.forEach(n=>n.parent=p); }
  get textContent() { return this.nodeValue ?? this.children.map(n=>n.textContent).join(''); }
  set textContent(value) { this.nodeValue=value; this.children=[]; }
}
class Document {
  createElement(tag) { return new Node(tag,this); }
  createTextNode(value) { return new Node(null,this,value); }
  createDocumentFragment() { return new Node('#fragment',this); }
  createTreeWalker(root) { const nodes=[]; const walk=n=>{if(!n.tagName)nodes.push(n);else n.children.forEach(walk)};walk(root);let i=-1;return {nextNode(){this.currentNode=nodes[++i];return !!this.currentNode}}; }
}

test('reference wrapping links actual DOM text nodes including code, without nested anchors', () => {
  const doc=new Document(), root=doc.createElement('div'), code=doc.createElement('code'), existing=doc.createElement('a');
  code.append(doc.createTextNode('a.md')); existing.append(doc.createTextNode('a.md'));
  root.append(doc.createTextNode('Rendered a.md '),code,existing);
  wrapReferences(root,[{text:'a.md',path:'/demo/a.md'}]);
  assert.equal(root.textContent,'Rendered a.md a.mda.md');
  assert.equal(root.children[1].className,'ref');
  assert.equal(root.children[1].dataset.path,'/demo/a.md');
  assert.equal(code.children[1].tagName,'A');
  assert.equal(code.children[1].href,'#file');
  assert.equal(existing.children.length,1);
  assert.equal(existing.children[0].tagName,undefined);
});

test('local Markdown links can only use recorded reference destinations', () => {
  const md=createMarkdown(markdownit);
  const html=md.render('[document](references/a.md)',{references:[{text:'references/a.md',path:'/demo/a.md'}]});
  assert.match(html, /class="ref" data-path="\/demo\/a.md" data-kind="file" href="#file"/);
  assert.doesNotMatch(md.render('[unknown](unknown.md)'), /href=/);
});

test('directory references retain their kind and wrap with an encoded VS Code href', () => {
  const path='/demo/中文 #?% &/', text='references/';
  const data={sources:{s:text},file_references:[{text_ref:{source_id:'s'},start:0,end:text.length,path,kind:'dir',owner_ids:['e']}]};
  const refs=referenceCandidates(data,text,{ownerIds:['e']});
  assert.deepEqual(refs,[{text,path,kind:'dir'}]);
  const doc=new Document(),root=doc.createElement('div');root.append(doc.createTextNode(text));
  wrapReferences(root,refs);
  const link=root.children.find(node=>node.tagName==='A');
  assert.equal(link.dataset.path,path);assert.equal(link.dataset.kind,'dir');
  const url=new URL(link.href);
  assert.equal(url.protocol,'vscode:');assert.equal(url.hostname,'file');
  assert.equal(decodeURIComponent(url.pathname),path);assert.equal(url.search,'');assert.equal(url.hash,'');
  const html=createMarkdown(markdownit).render('[folder](references/)',{references:refs});
  assert.match(html,/data-kind="dir"/);assert.match(html,/href="vscode:\/\/file\//);
});

test('a directory prefix never splits a full or unresolved file path into links', () => {
  const references=[{text:'references/',path:'/demo/references',kind:'dir'},
    {text:'references/a.md',path:'/demo/references/a.md',kind:'file'}];
  const text='references/ references/a.md references/missing.md nested/references/ references/.hidden references/.';
  assert.deepEqual(referenceMatches(text,references).map(ref=>ref.text),['references/','references/a.md','references/']);
});

test('directory clicks navigate, file clicks open the sidebar, and Command clicks reveal either kind', () => {
  const calls=[], actions={navigate:href=>calls.push(['navigate',href]),openFile:path=>calls.push(['sidebar',path])};
  for(const kind of ['dir','file']) {
    const ref={path:'/demo/references',kind};
    viewer.activateReference(ref,actions);
    assert.deepEqual(calls.pop(),kind==='dir'?['navigate','vscode://file/demo/references']:['sidebar',ref.path]);
    viewer.activateReference(ref,actions,true);
    assert.deepEqual(calls.pop(),['navigate',fileMenuActions(ref.path)[0].href]);
    assert.deepEqual(fileMenuActions(ref.path).map(action=>action.label),['在 Finder 中显示','在 VS Code 中打开','复制路径']);
  }
});

function fixture() {
  const categories = Object.fromEntries(['system','tools','injected','task'].map(key=>[key,{label:key,entries:[],item_ids:[]} ]));
  const img = n => ({id:`img${n}`,kind:'event',operation:'read',image_ids:['i'],path:`/tmp/scratchpad/${n}.png`,request_number:2});
  return {items:{}, requests:{
    'main/request/7':{id:'main/request/7',number:7,node_id:'main',params:{model:'claude-opus-5-5'}},
    'child/request/1':{id:'child/request/1',number:1,node_id:'child'},
    'child/request/2':{id:'child/request/2',number:2,node_id:'child'}
  }, nodes:[
    {id:'child',agent_id:'c',parent_id:'main',title:'writer',initial_context:{categories},request_ids:['child/request/1','child/request/2'],
     event_ids:['read','img1','img2','img3','write','edit','edit2'],segment_ids:['segment']},
    {id:'main',agent_id:null,request_ids:['main/request/7'],event_ids:['user','spawn'],leading_event_ids:[],segment_ids:['mseg']}
  ],events:{
    user:{id:'user',kind:'event',operation:'user',request_number:7},spawn:{id:'spawn',kind:'event',operation:'spawn',ends_segment:'spawn',child_node_id:'child',display_name:'writer',request_number:7},
    read:{id:'read',kind:'event',operation:'read',path:'/demo/a.md',request_number:1},
    img1:img(1),img2:img(2),img3:img(3),
    write:{id:'write',kind:'event',operation:'write',ends_segment:'write',path:'/demo/b.md',display_name:'b.md',request_number:2},
    edit:{id:'edit',kind:'event',operation:'edit',ends_segment:'write',path:'/demo/b.md',display_name:'b.md',request_number:2},
    edit2:{id:'edit2',kind:'event',operation:'edit',ends_segment:'write',path:'/demo/b.md',display_name:'b.md',request_number:2}
  },segments:{
    mseg:{id:'mseg',node_id:'main',end_kind:'spawn',event_ids:['user'],ending_event_ids:['spawn'],request_range:[7,7]},
    segment:{id:'segment',node_id:'child',end_kind:'write',event_ids:['read','img1','img2','img3'],ending_event_ids:['write','edit','edit2'],request_range:[1,2]}
  }};
}

test('tree is Agent → 上下文 → N 次操作 → 写入 X; the call segment holds the sub-Agent directly', () => {
  const {entries,roots,aliases}=buildTree(fixture());
  assert.equal(roots[0].id,'main');
  assert.deepEqual(entries.get('main').children.map(row=>row.id),['mseg']);
  const call=entries.get('mseg');
  assert(call.expanded && call.ops===1);
  assert.deepEqual(call.children.map(row=>row.id),['user','child']);
  assert.equal(aliases.get('spawn'),'mseg');
  const kids=entries.get('child').children;
  assert.deepEqual(kids.map(row=>row.kind),['initial','segment']);
  const seg=kids[1];
  assert(!seg.expanded && seg.ops===4);
  assert.deepEqual(seg.ends.map(e=>e.id),['write','edit','edit2']);
  assert.deepEqual(seg.children.map(row=>row.kind),['event','group','event','event','event']); // 输入在前，写入在最后
  assert.equal(seg.children[1].children.length,3);
  assert(!seg.children[0].roundStart && seg.children[1].roundStart); // 第 2 轮开头画线，段的第一行不画
  assert(!entries.get('child/initial').expanded);
});

test('a write that follows only model text joins the previous segment', () => {
  const data=fixture();
  data.events.late={id:'late',kind:'event',operation:'write',ends_segment:'write',path:'/demo/c.md',display_name:'c.md',request_number:3};
  data.events.say={id:'say',kind:'event',operation:'reply',request_number:3};
  data.segments.next={id:'next',node_id:'child',end_kind:'write',event_ids:['say'],ending_event_ids:['late'],request_range:[3,3]};
  data.nodes[0].segment_ids.push('next');
  const {entries}=buildTree(data);
  assert.deepEqual(entries.get('child').children.map(row=>row.id),['child/initial','segment']);
  assert.deepEqual(entries.get('segment').ends.map(e=>e.id),['write','edit','edit2','late']);
  assert.deepEqual(entries.get('segment').range,[1,3]);
});

test('consecutive code and command rows fold into one row; a single one stays', () => {
  const data=fixture();
  Object.assign(data.events,{
    e1:{id:'e1',kind:'event',operation:'exec',is_code:true,request_number:1},
    e2:{id:'e2',kind:'event',operation:'write',is_code:true,path:'/demo/x.js',request_number:1},
    e3:{id:'e3',kind:'event',operation:'exec',is_code:true,request_number:2}
  });
  data.segments.segment.event_ids=['e1','e2','read','e3'];
  const {entries}=buildTree(data), seg=entries.get('segment');
  assert.deepEqual(seg.children.map(row=>row.fold||row.id),['code','read','e3','write','edit','edit2']);
  const fold=seg.children[0];
  assert.equal(fold.event.display_name,'代码与命令 ×2');
  assert.deepEqual(fold.children.map(row=>row.id),['e1','e2']);
  assert.equal(entries.get('e2').parentId,fold.id);
});

test('an Agent without a closed segment lists its operations directly', () => {
  const data=fixture(), node={...data.nodes[0],id:'solo',agent_id:null,parent_id:null,segment_ids:[]};
  data.nodes=[node];
  const {roots}=buildTree(data);
  assert.deepEqual(roots[0].children.map(row=>row.kind),['initial','event','group','event','event','event']);
});

test('user files and changed files are highlighted; runtime files are not', () => {
  assert(viewer.isUserFile('/Users/me/work/project.md'));
  assert(viewer.isUserFile('/Users/me/.claude/CLAUDE.md'));
  for (const path of ['/private/tmp/claude-501/x/scratchpad/a.png','/Users/me/.claude/projects/p/s/tool-results/b.txt','/Users/me/.claude/projects/p/s.jsonl','', null]) assert(!viewer.isUserFile(path));
  assert.equal(viewer.shortName({operation:'list',display_name:'ls -la "a/b" "c/d" 2>/dev/null',item_ids:[]},{items:{}}),'b/、d/');
  for (const term of ['第 N 轮','N 次操作 → 写入 X','代码与命令 ×N']) assert(viewer.GLOSSARY.some(([t])=>t===term));
});

test('zero or absent event character counts leave the row empty', () => {
  for(const characters of [0,null,undefined]) assert.equal(viewer.eventCharacterCount({characters}),'');
  assert.equal(viewer.eventCharacterCount({characters:2941}),'2,941');
});

test('trace overview uses one box per agent, ordered by calls, including a lone main agent', () => {
  const data={nodes:[{id:'writer',parent_id:'main'},{id:'researcher',parent_id:'main'},{id:'main'}],events:{
    first:{request_number:2},second:{request_number:5}
  },edges:[
    {id:'second',kind:'dispatch',source_node_id:'main',target_node_id:'writer',source_event_id:'second'},
    {id:'file',kind:'file_flow',source_node_id:'researcher',target_node_id:'writer'},
    {id:'first',kind:'dispatch',source_node_id:'main',target_node_id:'researcher',source_event_id:'first'}
  ]};
  const graph=viewer.traceGraph(data);
  assert.deepEqual(graph.nodes.map(node=>node.id),['main','researcher','writer']);
  assert.equal(graph.edges.length,3);
  assert.deepEqual(viewer.traceGraph({nodes:[{id:'main'}],events:{},edges:[]}),{nodes:[{id:'main'}],edges:[]});
});

test('locating a leaf opens every ancestor without opening unrelated groups', () => {
  const {entries}=buildTree(fixture()), expanded=new Set(['unrelated']);
  assert.deepEqual(expandAncestors(entries,'read',expanded),['segment','child','mseg','main']);
  assert(!expanded.has('child/initial'));
});

test('merged writes keep names and operations without repetition or status labels', () => {
  const data=fixture(), parts=segmentParts(data.segments.segment,data.events);
  assert.deepEqual(parts,[{operation:'write',files:[{path:'/demo/b.md',name:'b.md'}]},{operation:'edit',files:[{path:'/demo/b.md',name:'b.md'}]}]);
});

test('execution details list files written by the same call, scoped to that agent', () => {
  const event={node_id:'a',tool_use_id:'call'};
  const file={path:'/demo/result.md'};
  const data={events:{write:{...event,written_files:[file]},edit:{...event,written_files:[file]},
    otherCall:{...event,tool_use_id:'another',written_files:[{path:'/demo/other.md'}]},
    otherAgent:{...event,node_id:'b',written_files:[{path:'/demo/b.md'}]}}};
  assert.deepEqual(viewer.relatedWrittenFiles(data,event),[file]);
  assert.deepEqual(viewer.relatedWrittenFiles(data,{}),[]);
});

test('context menu has exactly the three actions and safely encodes file URLs', () => {
  const path='/Users/example/中文 #?% &/a+b.md';
  const actions=fileMenuActions(path);
  assert.deepEqual(actions.map(a=>a.label),['在 Finder 中显示','在 VS Code 中打开','复制路径']);
  const reveal=new URL(actions[0].href);
  assert.equal(reveal.protocol,'agent-context-trace:'); assert.equal(reveal.hostname,'reveal');
  assert.equal(reveal.searchParams.get('path'),path);
  assert.equal(actions[0].href, 'agent-context-trace://reveal?path='+encodeURIComponent(path));
  const vscode=new URL(actions[1].href);
  assert.equal(vscode.protocol,'vscode:'); assert.equal(vscode.hostname,'file');
  assert.equal(decodeURIComponent(vscode.pathname),path); assert.equal(vscode.search,''); assert.equal(vscode.hash,'');
  assert.equal(actions[2].href,'#copy-path'); assert.equal(actions[2].path,path);
  assert.deepEqual(fileMenuActions('../relative.md'),[]);
  assert.deepEqual(fileMenuActions('/bad\0path'),[]);
});
