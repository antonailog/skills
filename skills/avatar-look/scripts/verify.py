#!/usr/bin/env python3
"""自动验收 avatar-look 产出目录：打开 demo.html，测 8 个方向看得对不对、快速画圈时跳转快不快、有没有报错。

用法：python3 verify.py <产出目录>/demo.html
依赖：playwright（pip install playwright）；优先用本机 Chrome（Playwright 自带的 Chromium 不支持 H.264）。

判定：测得到的方向全部在 ±45° 内、零报错、画圈时每秒完成跳转 ≥ 20 次、慢转一圈时头的方向一路跟住鼠标
（偏差 ≤ 45°、不倒退、每 30ms 最多走 3 帧）→ 退出码 0；否则 1。慢转这项拦的是「视频多转了一段没裁掉」：接缝处头会抢先扫过去再切回来，
快速画圈测不出来，因为每次跳转只走一两帧。
头像贴着窗口边缘时，鼠标放不到那一侧，那些方向记为 skipped，不算失败。
这只证明「能用」，顺不顺要人亲手晃鼠标判断。
"""
import asyncio, json, math, pathlib, sys
from playwright.async_api import async_playwright

DIRS = {'右': 0, '右下': 45, '下': 90, '左下': 135, '左': 180, '左上': 225, '上': 270, '右上': 315}


async def main(demo):
    async with async_playwright() as p:
        try:
            b = await p.chromium.launch(channel='chrome'); browser = 'Chrome'
        except Exception:
            b = await p.chromium.launch(); browser = 'Chromium（可能不支持 H.264，失败时装 Chrome 再测）'
        pg = await b.new_page(viewport={'width': 1280, 'height': 800})
        errs = []
        pg.on('console', lambda m: m.type == 'error' and errs.append(m.text))
        pg.on('pageerror', lambda e: errs.append(str(e)))
        await pg.goto(demo.as_uri())
        res = {'browser': browser}
        try:
            await pg.wait_for_function('window.AvatarLook && AvatarLook._state.ready()', timeout=20000)
        except Exception:
            res.update(ok=False, errors=errs + ['视频 20 秒内没加载好']); return res
        # 中间那个头像
        cx, cy, size = await pg.evaluate('''(() => { const el = document.querySelector('.a2') || document.querySelector('[data-avatar-look]');
            el.scrollIntoView({block: 'center'}); window.__it = el.__avatarLook; const r = el.getBoundingClientRect();
            return [r.left + r.width / 2, r.top + r.height / 2, r.width]; })()''')
        await pg.wait_for_timeout(300)
        # 鼠标出了窗口不会触发事件：每个方向的距离不超过到窗口边缘的距离；头像贴边时只测得到的方向
        def reach(rad):
            dx, dy = math.cos(rad), math.sin(rad)
            lim = [((1280 - 4 - cx) if dx > 0 else (cx - 4)) / abs(dx) if abs(dx) > 1e-6 else 1e9,
                   ((800 - 4 - cy) if dy > 0 else (cy - 4)) / abs(dy) if abs(dy) > 1e-6 else 1e9]
            return min(300, *lim)
        dead = size * 0.3 + 8
        ring = {f: a % 360 for f, a in await pg.evaluate('AvatarLook.model.ring')}

        wrong, skipped = {}, []
        for name, deg in DIRS.items():
            rad = math.radians(deg); r = reach(rad)
            if r < dead:
                skipped.append(name); continue
            await pg.mouse.move(cx + r * math.cos(rad), cy + r * math.sin(rad), steps=8)
            await pg.wait_for_timeout(1000)
            f = await pg.evaluate('__it.frame')
            got = ring.get(f)
            if got is None or abs((got - deg + 180) % 360 - 180) > 45:
                wrong[name] = {'frame': f, 'angle': got}

        await pg.evaluate('''window.__n = 0; window.__fr = []; __it.v.addEventListener('seeked', () => {
            window.__n++; window.__fr.push(Math.round(__it.v.currentTime * AVATAR_LOOK_DATA.fps - 0.5)); })''')
        R = min(reach(math.radians(d)) for d in range(0, 360, 15))
        edge = R < dead
        if edge:
            R = 300; cx, cy = 640, 400   # 头像贴边：画圈测不了这个头像，改测中心位置的鼠标移动（只看跳转速度）
        t0 = await pg.evaluate('performance.now()')
        for i in range(121):
            a = 2 * math.pi * 2 * i / 120
            await pg.mouse.move(cx + R * math.cos(a), cy + R * math.sin(a)); await pg.wait_for_timeout(12)
        t1 = await pg.evaluate('performance.now()')
        n, fr = await pg.evaluate('[window.__n, window.__fr]')
        order = {f: i for i, f in enumerate(ring)}
        jumps = [abs(order.get(y, 0) - order.get(x, 0)) for x, y in zip(fr, fr[1:])]
        jumps = sorted(min(j, len(ring) - j) for j in jumps) or [0]
        seeks = round(n * 1000 / (t1 - t0))

        # 慢转一整圈（约 6 秒，从正上方顺时针）：每一刻比较头朝的方向和鼠标方向，并看沿时间轴有没有倒退
        track_max, reverse, slow_step = None, None, None
        if not edge:
            samples = []
            await pg.mouse.move(cx, cy - R, steps=10); await pg.wait_for_timeout(800)   # 先停在起点等头转到位，免得把「追回起点」算成倒退
            for i in range(181):
                a = 2 * math.pi * i / 180 - math.pi / 2
                await pg.mouse.move(cx + R * math.cos(a), cy + R * math.sin(a)); await pg.wait_for_timeout(30)
                f = await pg.evaluate('__it.frame')
                samples.append((math.degrees(a) % 360, ring.get(f), order.get(f)))
            devs = [abs((g - m + 180) % 360 - 180) for m, g, _ in samples if g is not None]
            pos = [o for _, _, o in samples if o is not None]
            steps = [((y - x) % len(ring)) for x, y in zip(pos, pos[1:])]
            reverse = sum(1 for d in steps if d > len(ring) / 2)
            slow_step = max((d for d in steps if d <= len(ring) / 2), default=0)   # 慢转时每 30ms 本该只走零点几帧，一次走好几帧就是在抢跑
            track_max = round(max(devs)) if devs else None
        slow_ok = edge or (track_max is not None and track_max <= 45 and reverse == 0 and slow_step <= 3)
        res.update(directions_wrong=wrong, directions_skipped=skipped, circle_radius=round(R), seeks_per_sec=seeks, frame_step_median=jumps[len(jumps) // 2],
                   frame_step_max=jumps[-1], slow_track_err_max=track_max, slow_reverse=reverse, slow_step_max=slow_step, errors=errs,
                   ok=not wrong and not errs and seeks >= 20 and slow_ok)
        await b.close()
        return res


if __name__ == '__main__':
    demo = pathlib.Path(sys.argv[1]).expanduser().resolve()
    r = asyncio.run(main(demo))
    print(json.dumps(r, ensure_ascii=False, indent=2))
    sys.exit(0 if r.get('ok') else 1)
