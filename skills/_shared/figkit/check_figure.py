#!/usr/bin/env python3
"""按《出图规范》自动校验 SVG：最小字号、行长、只用主题里的颜色、strong／accent 面的用量；可选跑 whiteboard-cli --check。
用法：FIGKIT_THEME=themes/x.json python3 check_figure.py 图.svg [--wb]"""
import re,sys,json,pathlib,subprocess,unicodedata,os
HERE=pathlib.Path(__file__).resolve().parent
TH=json.loads(pathlib.Path(os.environ.get('FIGKIT_THEME',HERE/'themes/editorial-forest.json')).read_text(encoding='utf-8'))
allowed=set()
def add(v):
    if isinstance(v,str) and v.startswith('#'): allowed.add(v.lower())
    elif isinstance(v,dict): [add(x) for x in v.values()]
    elif isinstance(v,list): [add(x) for x in v]
add(TH)
svg=pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'); issues=[]
fs=[int(float(x)) for x in re.findall(r'font-size="([\d.]+)"',svg)]
if fs and min(fs)<16: issues.append(f'最小字号 {min(fs)} < 16')
texts=re.findall(r'<text[^>]*x="([\d.]+)"[^>]*font-size="([\d.]+)"[^>]*>([^<]*)</text>',svg)
def cjk(t): return sum(1 for c in t if unicodedata.east_asian_width(c) in ('W','F'))
long=[t for x,f,t in texts if float(f)<=20 and (cjk(t)>60 if float(x)<=60 else cjk(t)>30)]
if long: issues.append(f'{len(long)} 行超长（卡内 >30 字或整宽 >60 字），如「{long[0][:20]}…」')
used=set(c.lower() for c in re.findall(r'(?:fill|stroke)="(#[0-9a-fA-F]{6})"',svg))
bad=[c for c in used if c not in allowed]
if bad: issues.append(f'用了主题之外的颜色：{bad}')
H=int(float(re.search(r'height="([\d.]+)"',svg).group(1)))
rects=[(float(y),float(w),float(h),c.lower()) for y,w,h,c in re.findall(r'<rect[^>]*y="([\d.]+)"[^>]*width="([\d.]+)"[^>]*height="([\d.]+)"[^>]*fill="(#[0-9a-fA-F]{6})"',svg)]
sf=TH['surfaces']; strong=(sf['strong']['fill'] or '').lower(); accent=(sf['accent']['fill'] or '').lower()
for win in range(0,H,900):
    ns=sum(1 for y,w,h,c in rects if c==strong and h>60 and w>60 and win<=y<win+900)
    na=sum(1 for y,w,h,c in rects if c==accent and c!=(sf['base']['fill'] or '').lower() and h>60 and w>60 and win<=y<win+900)
    if ns>2: issues.append(f'{win}-{win+900}px 内 strong 面 {ns} 张 > 2')
    if na>2: issues.append(f'{win}-{win+900}px 内 accent 面 {na} 张 > 2')
# —— 版面检查：文字超出所在形状、数字被拆到两行（2026-10-23 加：之前这两类只能靠肉眼在预览里发现）。
# 不查英文拆行：figkit 折行保持英文词完整，英文|英文 的行界都在空格处，查了只会误报。
def tw(t,fs): return sum(1.0 if unicodedata.east_asian_width(c) in ('W','F') else 0.6 for c in t)*fs
TX=[]
for m in re.finditer(r'<text[^>]*>[^<]*</text>',svg):
    e=m.group(0); g=lambda k,d=None: (re.search(k+r'="([^"]+)"',e) or [None,d])[1]
    t=re.sub(r'<[^>]+>','',e)
    if not t.strip(): continue
    TX.append({'x':float(g('x',0)),'y':float(g('y',0)),'fs':float(g('font-size',16)),'anchor':g('text-anchor','start'),'t':t})
RC=[]
for m in re.finditer(r'<rect[^>]*/?>',svg):
    e=m.group(0); g=lambda k: re.search(r'\b'+k+r'="([\d.]+)"',e)
    if not (g('x') and g('y') and g('width') and g('height')) or 'id="canvas"' in e: continue
    RC.append(tuple(float(g(k).group(1)) for k in ('x','y','width','height')))
over=[]
for T in TX:
    w=tw(T['t'],T['fs']); left={'middle':T['x']-w/2,'end':T['x']-w}.get(T['anchor'],T['x']); cy=T['y']-T['fs']*0.35
    box=[r for r in RC if r[0]<=T['x']<=r[0]+r[2] and r[1]<=cy<=r[1]+r[3] and r[2]>10 and r[3]>10]
    if not box: continue
    rx,ry,rw,rh=min(box,key=lambda r:r[2]*r[3])
    if left<rx-1 or left+w>rx+rw+1: over.append(T['t'][:16])
if over: issues.append(f'{len(over)} 处文字超出所在形状，如「{over[0]}…」')
split=[]
cols={}
for T in TX: cols.setdefault((round(T['x']),T['anchor']),[]).append(T)
for col in cols.values():
    col.sort(key=lambda T:T['y'])
    for a,b in zip(col,col[1:]):
        if 0<b['y']-a['y']<=a['fs']*1.9 and re.search(r'[0-9.,]$',a['t']) and re.match(r'^[0-9%]',b['t']): split.append(a['t'][-6:]+'|'+b['t'][:4])
if split: issues.append(f'{len(split)} 处数字被拆到两行，如「{split[0]}」')
out={'file':sys.argv[1],'theme':TH['name'],'height':H,'texts':len(texts),'issues':issues}
if '--wb' in sys.argv:
    r=subprocess.run(['npx','-y','@larksuite/whiteboard-cli@^0.2.13','-i',sys.argv[1],'-f','svg','--check'],capture_output=True,text=True).stdout
    try:
        c=json.loads(r[r.find('{'):])['data']['check']; out['whiteboard']={'errors':c['errors'],'warnings':c['warnings'],'issues':[i['message'][:80] for i in c.get('issues',[])][:5]}
    except Exception: out['whiteboard']='check failed to parse'
print(json.dumps(out,ensure_ascii=False,indent=1)); sys.exit(1 if issues else 0)
