#!/usr/bin/env python3
"""编辑模式服务（只监听本机）：打开讲稿，按 E 进编辑模式。

用法：python3 serve.py <讲稿目录> [--port 4350] [--notes <改稿目录>]

- 讲稿文件本身不带编辑代码：编辑脚本只在这里打开 index.html 时注入
- 改字、删除、调样式、拖动：写回 index.html，只替换 <div id="stage"> 到 </div><!-- /stage --> 之间；
  文件在别处被改过就拒绝保存（版本检查）；每 5 分钟最多备份一次到 <改稿>/备份/
- 批注：<改稿>/批注.json，截图存 <改稿>/图/
"""
import argparse
import json
import secrets
import shutil
import socket
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

SKILL = Path(__file__).resolve().parent.parent
EDITOR = SKILL / 'assets' / 'engine' / 'editor.js'
OPEN, CLOSE = '<div id="stage">', '</div><!-- /stage -->'
EXT = {'image/png': '.png', 'image/jpeg': '.jpg', 'image/gif': '.gif', 'image/webp': '.webp'}


def free_port(start):
    for p in range(start, start + 50):
        with socket.socket() as s:
            if s.connect_ex(('127.0.0.1', p)) != 0:
                return p
    raise SystemExit(f'{start}—{start + 49} 的端口都被占了，用 --port 指定一个')


def make_handler(deck: Path, notes: Path, port: int):
    index = deck / 'index.html'
    state = {'backup': 0.0}
    token = secrets.token_urlsafe(24)   # 只有本服务发出去的页面知道；别的网页发来的写请求带不上它
    hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
    lock = threading.Lock()

    def ver():
        return str(index.stat().st_mtime_ns)

    def read_comments():
        f = notes / '批注.json'
        return json.loads(f.read_text('utf-8')) if f.exists() else []

    def write_comments(cs):
        notes.mkdir(parents=True, exist_ok=True)
        (notes / '批注.json').write_text(json.dumps(cs, ensure_ascii=False, indent=2), 'utf-8')

    class H(SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(deck), **k)

        def log_message(self, *a):
            pass

        def reply(self, data, ctype='application/json; charset=utf-8', code=200):
            if not isinstance(data, bytes):
                data = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.headers.get('Host') not in hosts:   # 防 DNS 重绑定：只认本机地址
                return self.send_error(403)
            p = unquote(urlparse(self.path).path)
            if p in ('/', '/index.html'):
                html = index.read_text('utf-8')
                tag = f'<script>window.__DECK_VER = "{ver()}"; window.__DECK_TOKEN = "{token}";</script><script src="/__edit/editor.js"></script>\n</body>'
                return self.reply(html.replace('</body>', tag, 1).encode(), 'text/html; charset=utf-8')
            if p == '/__edit/editor.js':
                return self.reply(EDITOR.read_bytes(), 'text/javascript; charset=utf-8')
            if p == '/__api/comments':
                return self.reply(read_comments())
            if p.startswith('/__notes/'):
                f = (notes / p[len('/__notes/'):]).resolve()
                if notes.resolve() in f.parents and f.is_file():
                    return self.reply(f.read_bytes(), self.guess_type(str(f)))
                return self.send_error(404)
            return super().do_GET()

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get('Content-Length', 0) or 0))
            if self.headers.get('Host') not in hosts or not secrets.compare_digest(self.headers.get('X-Deck-Token', ''), token):
                return self.reply({'ok': False, 'err': '口令不对：请从编辑服务打开的页面里改'}, code=403)
            try:
                with lock:   # 两次保存同时到达时一个一个来，版本检查才可靠
                    return self.post(urlparse(self.path).path, body)
            except (ValueError, KeyError, TypeError, AttributeError) as e:
                return self.reply({'ok': False, 'err': f'请求格式不对：{e}'}, code=400)

        def obj(self, body, *keys):
            d = json.loads(body)
            if not isinstance(d, dict) or any(k not in d for k in keys):
                raise ValueError('要一个带 ' + '、'.join(keys) + ' 的对象')
            return d

        def post(self, p, body):
            if p == '/__api/save':
                d = self.obj(body, 'stage', 'ver')
                if not isinstance(d['stage'], str):
                    raise ValueError('stage 要是文字')
                if d.get('ver') != ver():
                    return self.reply({'ok': False, 'err': 'changed'}, code=409)
                html = index.read_text('utf-8')
                i, j = html.find(OPEN), html.find(CLOSE)
                if i < 0 or j < 0:
                    return self.reply({'ok': False, 'err': f'讲稿里找不到 {OPEN} 或 {CLOSE}'}, code=500)
                if time.time() - state['backup'] > 300:
                    b = notes / '备份'
                    b.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(index, b / time.strftime('index-%m%d-%H%M%S.html'))
                    state['backup'] = time.time()
                index.write_text(html[:i + len(OPEN)] + '\n' + d['stage'].strip() + '\n' + html[j:], 'utf-8')
                return self.reply({'ok': True, 'ver': ver()})
            if p == '/__api/comments/add':
                cs = read_comments()
                c = self.obj(body, 'id', 'text')
                c.setdefault('images', [])
                cs.append(c)
                write_comments(cs)
                return self.reply(cs)
            if p == '/__api/comments/del':
                cid = self.obj(body, 'id')['id']
                cs = [c for c in read_comments() if c.get('id') != cid]
                write_comments(cs)
                return self.reply(cs)
            if p == '/__api/image':
                d = notes / '图'
                d.mkdir(parents=True, exist_ok=True)
                name = time.strftime('%m%d-%H%M%S-') + f'{time.time_ns() % 10**6:06d}' + EXT.get(self.headers.get('Content-Type', ''), '.png')
                (d / name).write_bytes(body)
                return self.reply({'path': '图/' + name})
            return self.send_error(404)

    return H


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('deck', help='讲稿目录（里面有 index.html）')
    ap.add_argument('--port', type=int, default=4350)
    ap.add_argument('--notes', help='批注和备份放哪，默认讲稿目录旁边的 改稿/')
    a = ap.parse_args()
    deck = Path(a.deck).expanduser().resolve()
    if not (deck / 'index.html').exists():
        raise SystemExit(f'{deck}/index.html 不存在')
    html = (deck / 'index.html').read_text('utf-8')
    if OPEN not in html or CLOSE not in html:
        raise SystemExit(f'讲稿里要有 {OPEN} 和 {CLOSE} 两个标记，编辑模式靠它们只写回内容部分')
    notes = Path(a.notes).expanduser().resolve() if a.notes else deck.parent / '改稿'
    port = free_port(a.port)
    print(f'编辑模式：http://127.0.0.1:{port}/  （按 E 进编辑模式，Ctrl+C 停止）')
    print(f'批注写到：{notes / "批注.json"}')
    ThreadingHTTPServer(('127.0.0.1', port), make_handler(deck, notes, port)).serve_forever()


if __name__ == '__main__':
    main()
