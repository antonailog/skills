#!/usr/bin/env python3
"""figkit v2：按《出图规范》把图稿渲染成 SVG。主题模型来自 beautiful-feishu-whiteboard：画布 + 四种面（base／strong／accent／plain），
文字颜色跟随所在面。用法：FIGKIT_THEME=themes/editorial-forest.json python3 figkit.py 图稿.json 输出.svg
用量纪律：每个模块最多一张 strong、一张 accent，其余 base；颜色靠面的切换，不靠大面积填充。"""
import json,math,sys,unicodedata,pathlib,os
HERE=pathlib.Path(__file__).resolve().parent
TH=json.loads(pathlib.Path(os.environ.get('FIGKIT_THEME',HERE/'themes/editorial-forest.json')).read_text(encoding='utf-8'))
FONT='Noto Sans SC'; W=1600; M=60; CW=W-2*M; GAP=24; RX=TH.get('radius',6)
PUNCT='，、。；：）」》%'
def tw(t,fs): return sum(1.0 if unicodedata.east_asian_width(c) in ('W','F') else 0.6 for c in t)*fs
def tokens(t):
    out=[];cur=''
    for ch in t:
        if unicodedata.east_asian_width(ch) in ('W','F'):
            if cur: out.append(cur);cur=''
            out.append(ch)
        elif ch==' ':
            if cur: out.append(cur);cur=''
            out.append(' ')
        else: cur+=ch
    if cur: out.append(cur)
    return out
def wrap(t,fs,maxw):
    lines=[];cur=''
    for tok in tokens(t):
        if tok==' ': cur+=' '; continue
        if tw(cur+tok,fs)>maxw and cur.strip() and tok not in PUNCT: lines.append(cur.rstrip());cur=tok
        else: cur+=tok
    if cur.strip(): lines.append(cur.rstrip())
    return lines
def esc(s): return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
ROLE={'strong':'strong','primary':'strong','accent':'accent','accentDeep':'accent','base':'base','surface':'base','surface2':'base','plain':'plain'}
class SVG:
    def __init__(s): s.p=[]; s.n=0
    def id(s,k): s.n+=1; return f'{k}{s.n}'
    def rect(s,x,y,w,h,fill,stroke=None,rx=None,sw=2):
        if fill is None and stroke is None: return
        st=f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ''
        f=fill or 'none'
        s.p.append(f'<rect id="{s.id("r")}" x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="{RX if rx is None else rx}" fill="{f}"{st}/>')
    def circle(s,x,y,r,fill): s.p.append(f'<circle id="{s.id("c")}" cx="{x:.0f}" cy="{y:.0f}" r="{r}" fill="{fill}"/>')
    def text(s,x,y,t,fs,color,weight=400,anchor='start'):
        s.p.append(f'<text id="{s.id("t")}" x="{x:.0f}" y="{y:.0f}" font-family="{FONT}" font-size="{fs}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{esc(t)}</text>')
    def line(s,pts,color,sw=2):
        d='M'+' L'.join(f'{x:.0f} {y:.0f}' for x,y in pts); s.p.append(f'<path id="{s.id("l")}" d="{d}" stroke="{color}" stroke-width="{sw}" fill="none"/>')
    def arrow(s,pts,color=None,sw=2.5):
        # 原生连接器：line/polyline + marker-end，画板转成带箭头的 connector（whiteboard-cli 0.2.13 实测）
        color=color or TH['marks']['arrow']
        if len(pts)==2:
            (x1,y1),(x2,y2)=pts; s.p.append(f'<line id="{s.id("a")}" x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" stroke="{color}" stroke-width="{sw}" marker-end="url(#arrow)"/>')
        else:
            s.p.append(f'<polyline id="{s.id("a")}" points="{" ".join(f"{x:.0f},{y:.0f}" for x,y in pts)}" fill="none" stroke="{color}" stroke-width="{sw}" marker-end="url(#arrow)"/>')
    def dump(s,path,h):
        body='\n'.join(s.p)
        defs='<defs><marker id="arrow" markerWidth="12" markerHeight="12" refX="9" refY="4" orient="auto" markerUnits="strokeWidth"><path d="M0 0 L10 4 L0 8 z"/></marker></defs>\n'
        pathlib.Path(path).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h:.0f}" viewBox="0 0 {W} {h:.0f}">\n{defs}<rect id="canvas" x="0" y="0" width="{W}" height="{h:.0f}" fill="{TH["canvas"]}"/>\n{body}\n</svg>',encoding='utf-8')
# ---------- 卡片 ----------
def _cols(w,fs):
    return 3 if w>1100 else (2 if w>760 else 1)
def _wrapped(w,lines,fs):
    """返回每栏的折行结果列表。宽卡两栏：先按栏宽折行，再把总行数对半分。"""
    n=_cols(w,fs); colw=(w-72-(n-1)*28)/n
    flat=[]
    import re as _re
    for l in lines:
        parts=[x for x in _re.split(r'(?<=[；。])',l) if x.strip()] if n>1 and sum(1 for c in l if unicodedata.east_asian_width(c) in ('W','F'))>30 else [l]
        for part in parts:
            for ln in wrap(part,fs,colw): flat.append(ln)
        flat.append(None)   # 条目间空行标记
    while flat and flat[-1] is None: flat.pop()
    if n==1: return [flat]
    half=(len(flat)+1)//2
    while half<len(flat) and flat[half] is not None and flat[half-1] is not None and False: half+=1
    return [flat[:half],flat[half:]]
def card_h(w,title,big,lines,fs=18):
    h=22+(28*len(wrap(title,20,min(w-72,600))) if title else 0)+(44 if big else 0)
    cols=_wrapped(w,list(lines),fs); rows=max((len(c) for c in cols),default=0)
    nonempty=max((sum(1 for x in c if x is not None) for c in cols),default=0); blanks=rows-nonempty
    return h+nonempty*26+blanks*8+22
def card(s,x,y,w,role,title=None,big=None,lines=(),fs=18,h=None):
    sf=TH['surfaces'][ROLE.get(role,'base')]; hh=h or card_h(w,title,big,lines,fs)
    s.rect(x,y,w,hh,sf['fill'],sf['border'])
    cy=y+22
    if title:
        for ln in wrap(title,20,min(w-72,600)): s.text(x+24,cy+17,ln,20,sf['heading'],700); cy+=28
    if big:
        bfs=34
        while tw(big,bfs)>w-56 and bfs>22: bfs-=2
        s.text(x+24,cy+32,big,bfs,sf['big'],700); cy+=44
    cols=_wrapped(w,list(lines),fs); n=len(cols); colw=(w-72-(n-1)*28)/n
    for ci,col in enumerate(cols):
        yy=cy; cx=x+24+ci*(colw+28)
        for ln in col:
            if ln is None: yy+=8; continue
            s.text(cx,yy+fs*0.85+3,ln,fs,sf['text']); yy+=26
    return hh
def row(s,y,items,arrows=False):
    tot=sum(i.get('span',1) for i in items); ws=[(CW-GAP*(len(items)-1))*i.get('span',1)/tot for i in items]
    hs=[card_h(w,i.get('text'),i.get('big'),i.get('lines',())) for w,i in zip(ws,items)]; H=max(hs); x=M
    for k,(w,i) in enumerate(zip(ws,items)):
        card(s,x,y,w,i.get('role','base'),i.get('text'),i.get('big'),i.get('lines',()),h=H)
        if arrows and k<len(items)-1: s.arrow([(x+w+2,y+H/2),(x+w+GAP-2,y+H/2)])
        x+=w+GAP
    return y+H
def note(s,y,t,fs=16):
    for ln in wrap(t,fs,CW): s.text(M,y+fs,ln,fs,TH['text']['muted']); y+=24
    return y+4
# ---------- 信息图 ----------
def render_infographic(spec,out):
    s=SVG(); y=M; mk=TH['marks']
    s.text(M,y+34,spec['title'],40,TH['text']['heading'],700); y+=58
    if spec.get('subtitle'): s.text(M,y+18,spec['subtitle'],20,TH['text']['body']); y+=44
    mods=spec.get('modules',[])
    if spec.get('route',True) and mods:
        pw=(CW-(len(mods)-1)*20)/len(mods); x=M
        for k,mo in enumerate(mods):
            on=(k==0); s.rect(x,y,pw,44,mk['route_on'] if on else mk['route_off'],None,rx=3); s.text(x+pw/2,y+29,mo.get('label',mo['title'][:8]),18,mk['route_on_text'] if on else mk['route_off_text'],700,'middle')
            if k<len(mods)-1: s.arrow([(x+pw+2,y+22),(x+pw+18,y+22)])
            x+=pw+20
        y+=44+40
    for k,mo in enumerate(mods,1):
        s.circle(M+22,y+22,22,mk['number_fill']); s.text(M+22,y+30,f'{k:02d}',20,mk['number_text'],700,'middle')
        s.text(M+60,y+31,mo['title'],26,TH['text']['heading'],700); y+=50
        s.line([(M,y),(W-M,y)],TH['rule'],TH.get('rule_width',2)); y+=24
        groups=[]
        for it in mo.get('items',[]):
            g=it.get('group','_')
            if not groups or groups[-1][0]!=g: groups.append((g,[]))
            groups[-1][1].append(it)
        nexts={(r['from'],r['to']) for r in mo.get('relations',[]) if r.get('kind')=='下一步'}
        for g,items in groups:
            arrows=any((a['id'],b['id']) in nexts for a,b in zip(items,items[1:]))
            y=row(s,y,items,arrows)+GAP
        for n in mo.get('notes',[]): y=note(s,y,n)
        y+=20
    for n in spec.get('notes',[]): y=note(s,y,n)
    s.dump(out,y+40); return y+40
# ---------- 柱状图 ----------
def fmt(v): return f'{v:,.2f}'.rstrip('0').rstrip('.') if isinstance(v,float) else f'{v:,}'
def render_bar(spec,out):
    s=SVG(); y=M; tx=TH['text']
    s.text(M,y+28,spec['title'],26,tx['heading'],700); y+=40
    if spec.get('subtitle'): s.text(M,y+16,spec['subtitle'],18,tx['muted']); y+=30
    series=spec.get('series',['值']); items=spec['items']; unit=spec.get('unit',''); cols=TH['data'][:len(series)]
    if len(series)>1:
        x=M
        for c,nm in zip(cols,series): s.rect(x,y+4,18,18,c,None,rx=3); s.text(x+26,y+19,nm,18,tx['body']); x+=26+tw(nm,18)+40
        y+=40
    ph=440; px=M+70; pw=CW-70; top=y+20; base=top+ph
    vmax=max(v for it in items for v in it['values']); mag=10**math.floor(math.log10(vmax)); vmax=math.ceil(vmax/mag)*mag
    for k in range(5):
        gy=base-ph*k/4; s.line([(px,gy),(px+pw,gy)],TH['rule'],1); s.text(px-10,gy+6,fmt(round(vmax*k/4)),16,tx['muted'],400,'end')
    n=len(items); gw=pw/n; bw=min(90,(gw-40)/len(series))
    for i,it in enumerate(items):
        gx=px+i*gw+gw/2-bw*len(series)/2
        for j,(v,c) in enumerate(zip(it['values'],cols)):
            bh=ph*v/vmax; x=gx+j*bw
            s.rect(x+4,base-bh,bw-8,bh,c,None,rx=3); s.text(x+bw/2,base-bh-10,fmt(v),18,tx['body'],700,'middle')
        s.text(px+i*gw+gw/2,base+28,it['text'],18,tx['body'],700,'middle')
        if it.get('big'): s.text(px+i*gw+gw/2,base+56,it['big'],20,TH['surfaces']['accent']['heading'],700,'middle')
    if unit: s.text(px,top-4,unit,16,tx['muted'])
    y=base+80
    for nt in spec.get('notes',[]): y=note(s,y,nt)
    s.dump(out,y+30); return y+30
# ---------- 层级图（骨架图）：items 按 group 分章，每章一行；章名为 strong 小胶囊，单元为 base 卡 ----------
def render_hierarchy(spec,out):
    s=SVG(); y=M; mk=TH['marks']
    s.text(M,y+34,spec['title'],30,TH['text']['heading'],700); y+=50
    if spec.get('subtitle'): s.text(M,y+18,spec['subtitle'],20,TH['text']['body']); y+=40
    y+=10
    groups=[]
    for it in spec['items']:
        g=it.get('group','')
        if not groups or groups[-1][0]!=g: groups.append((g,[]))
        groups[-1][1].append(it)
    labw=270; gap=GAP; ROWMAX=3
    for g,items in groups:
        nrow=math.ceil(len(items)/ROWMAX); per=math.ceil(len(items)/nrow)
        rows=[items[i:i+per] for i in range(0,len(items),per)]
        uw=(CW-labw-gap-(per-1)*gap)/per
        rhs=[max(22+len(wrap(it['text'],20,uw-140))*28+22 for it in r) for r in rows]
        Htot=sum(rhs)+gap*(len(rows)-1)
        s.rect(M-16,y-12,CW+32,Htot+24,TH['surfaces']['base']['fill'],None,rx=10)
        gl=(wrap(g,18,labw-60) if tw(g,18)>labw-60 else [g])[:2]; pill_h=28+26*len(gl)
        s.rect(M,y+(Htot-pill_h)/2,labw,pill_h,mk['route_on'],None,rx=6)
        for i,ln in enumerate(gl): s.text(M+labw/2,y+(Htot-pill_h)/2+14+26*i+16,ln,18,mk['route_on_text'],700,'middle')
        ry=y
        for r,H in zip(rows,rhs):
            x=M+labw+gap
            for it in r:
                sf=TH['surfaces']['base']; s.rect(x,ry,uw,H,TH['canvas'],sf['border'])
                cy=ry+22
                for ln in wrap(it['text'],20,uw-140): s.text(x+24,cy+17,ln,20,sf['text'],700); cy+=28
                x+=uw+gap
            ry+=H+gap
        y+=Htot+36
    for n in spec.get('notes',[]): y=note(s,y,n)
    s.dump(out,y+40); return y+40
# ---------- 条件汇合：items 中 role=strong 的一项是汇合结果，其余为条件；箭头从条件指向结果 ----------
def render_convergence(spec,out):
    s=SVG(); y=M
    s.text(M,y+28,spec['title'],26,TH['text']['heading'],700); y+=60
    conds=[it for it in spec['items'] if ROLE.get(it.get('role','base'))!='strong']; res=[it for it in spec['items'] if ROLE.get(it.get('role','base'))=='strong'][0]
    n=len(conds); cw=(CW-(n-1)*40)/n; hs=[card_h(cw,it.get('text'),it.get('big'),it.get('lines',())) for it in conds]; H=max(hs); x=M; cy=y
    for it,h in zip(conds,hs): card(s,x,cy,cw,'base',it.get('text'),it.get('big'),it.get('lines',()),h=H); x+=cw+40
    ry=cy+H+70; rw=min(CW,760); rx=(W-rw)/2
    for i in range(n):
        cx=M+i*(cw+40)+cw/2
        if abs(cx-W/2)<1: s.arrow([(cx,cy+H),(cx,ry)])
        else: s.arrow([(cx,cy+H),(cx,ry-30),(W/2,ry-30),(W/2,ry)])
    rh=card(s,rx,ry,rw,'strong',res.get('text'),res.get('big'),res.get('lines',()))
    y=ry+rh+30
    for nt in spec.get('notes',[]): y=note(s,y,nt)
    s.dump(out,y+30); return y+30
# ---------- 流程图：group=steps 的 items 横排带箭头；其余 group 作为分支行，总线从步骤行引出 ----------
def render_flow(spec,out):
    s=SVG(); y=M; mk=TH['marks']
    s.text(M,y+28,spec['title'],26,TH['text']['heading'],700); y+=60
    steps=[it for it in spec['items'] if it.get('group','steps')=='steps']; others=[it for it in spec['items'] if it.get('group','steps')!='steps']
    n=len(steps); sw=(CW-(n-1)*80)/n; hs=[card_h(sw,it.get('text'),None,it.get('lines',()))+16 for it in steps]; H=max(hs); x=M; sy=y
    for k,(it,h) in enumerate(zip(steps,hs)):
        sf=TH['surfaces']['base']; s.rect(x,sy,sw,H,sf['fill'],sf['border'])
        s.circle(x+34,sy+34,18,mk['number_fill']); s.text(x+34,sy+41,str(k+1),18,mk['number_text'],700,'middle')
        s.text(x+62,sy+41,it.get('text',''),20,sf['heading'],700); cy=sy+22+38
        for l in it.get('lines',()):
            for ln in wrap(l,18,sw-72): s.text(x+24,cy+18,ln,18,sf['text']); cy+=26
        if k<n-1: s.arrow([(x+sw+8,sy+H/2),(x+sw+72,sy+H/2)])
        x+=sw+80
    y=sy+H
    if others:
        by=y+70; m=len(others); bw=(CW-(m-1)*24)/m; bh=[card_h(bw,it.get('text'),it.get('big'),it.get('lines',())) for it in others]; BH=max(bh)
        link=spec.get('branch_link',True)
        if link:
            s.line([(M+bw/2,by-40),(M+(m-1)*(bw+24)+bw/2,by-40)],mk['arrow'],2.5); s.arrow([(W/2,y),(W/2,by-40)])
        else:
            s.line([(M,by-34),(W-M,by-34)],TH['rule'],TH.get('rule_width',2)); s.text(M,by-46,spec.get('branch_label','对照'),18,TH['text']['heading'],700)
        x=M
        for it,h in zip(others,bh):
            if link: s.arrow([(x+bw/2,by-40),(x+bw/2,by)])
            card(s,x,by,bw,it.get('role','base'),it.get('text'),it.get('big'),it.get('lines',()),h=BH); x+=bw+24
        y=by+BH
    y+=30
    for nt in spec.get('notes',[]): y=note(s,y,nt)
    s.dump(out,y+30); return y+30
# ---------- 组成条：items 带 value，按比例画一条横条；第一段 strong、第二段 accent、其余 base ----------
def render_composition(spec,out):
    s=SVG(); y=M
    s.text(M,y+28,spec['title'],26,TH['text']['heading'],700); y+=60
    segs=[it for it in spec['items'] if 'value' in it]; total=spec.get('total') or sum(it['value'] for it in segs)
    bx=M; by=y; bh=96; x=bx; roles=['strong','accent','base','base']
    for k,it in enumerate(segs):
        w=CW*it['value']/total; sf=TH['surfaces'][roles[k]]
        s.rect(x,by,w,bh,sf['fill'],sf['border'] if roles[k]=='base' else None,rx=4)
        if w>220:
            s.text(x+20,by+40,it['text'],22,sf['heading'],700); s.text(x+20,by+72,it.get('big',''),18,sf['text'])
        else:
            s.text(x+w/2,by+bh+24,it['text'],18,TH['text']['body'],700,'middle')
        x+=w
    y=by+bh+60
    extra=[it for it in spec['items'] if 'value' not in it]
    if extra: y=row(s,y,extra)+20
    for nt in spec.get('notes',[]): y=note(s,y,nt)
    s.dump(out,y+30); return y+30
def render(spec,out):
    t=spec['type']
    if t=='信息图': return render_infographic(spec,out)
    if t=='柱状图': return render_bar(spec,out)
    if t=='层级图': return render_hierarchy(spec,out)
    if t=='条件汇合': return render_convergence(spec,out)
    if t=='流程图': return render_flow(spec,out)
    if t=='组成条': return render_composition(spec,out)
    raise SystemExit(f'figkit 还没有 {t} 模板')
if __name__=='__main__':
    spec=json.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')); h=render(spec,sys.argv[2]); print(sys.argv[2],W,int(h))
