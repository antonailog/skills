#!/usr/bin/env python3
"""把「头绕一圈」的形象视频做成 avatar-look 组件素材，并自检视频是否可用。

用法（mediapipe 只有 Python 3.12 及以下的轮子，用 uv 临时环境跑）：
  uv run --no-project --python 3.12 --with "mediapipe==0.10.14" --with "opencv-python<4.11" --with "numpy<2" \
      python process_video.py <视频> --out <产出目录> [--crop W:H:X:Y] [--size 480]

产出（写进 --out）：
  avatar.mp4    以脸为中心的方块，H.264 每帧都是关键帧（-g 1），跳到任意一帧都快
  poster.webp   第 0 帧正脸：加载前的占位、鼠标离开后的静态头像
  poses.js      window.AVATAR_LOOK_DATA = {fps, front, poses, ring}；ring 是绕圈那段的 [帧号, 屏幕方向角]
  check.png     九宫格核对图：8 个方向 + 正脸各取一帧，给人看方向对不对
  report.json   自检结果

退出码：0 通过；2 自检不通过（视频要重新生成，原因打印在最后）；1 运行出错。
"""
import argparse, json, math, pathlib, subprocess, sys, tempfile
import cv2, mediapipe as mp, numpy as np

FACE_TO_CROP = 2.65     # 方块边长 = 脸宽（左右脸颊关键点距离）× 此系数：帽顶、下巴到锁骨都在框里
RING_MIN_R = 0.8        # 头转幅到位（归一化半径 ≥ 0.8）才算进入绕圈段
MAX_GAP_DEG = 60        # 绕圈段首尾之间没拍到的角度超过它，说明视频没转满一圈
MIN_DETECT = 0.9        # 人脸识别率下限
X264 = ['-c:v', 'libx264', '-preset', 'slow', '-crf', '22', '-g', '1', '-pix_fmt', 'yuv420p', '-movflags', '+faststart']


def sh(*cmd):
    subprocess.run(cmd, check=True)


def probe(video):
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                          'stream=width,height,r_frame_rate', '-of', 'json', str(video)],
                         capture_output=True, text=True, check=True).stdout
    s = json.loads(out)['streams'][0]
    num, den = s['r_frame_rate'].split('/')
    return s['width'], s['height'], int(num) / int(den)


def landmarks(fm, img):
    r = fm.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    if not r.multi_face_landmarks:
        return None
    h, w = img.shape[:2]
    L = r.multi_face_landmarks[0].landmark
    return lambda i: (L[i].x * w, L[i].y * h)


def auto_crop(fm, src_dir, W, H):
    """全片人脸中心和脸宽取中位数，定一个固定方块；人在画面里怎么动都用同一个框。"""
    cs, ws = [], []
    for p in sorted(src_dir.glob('f*.png'))[::3]:
        P = landmarks(fm, cv2.imread(str(p)))
        if P is None:
            continue
        (lx, ly), (rx, ry) = P(234), P(454)
        cs.append(((lx + rx) / 2, (P(10)[1] + P(152)[1]) / 2)); ws.append(abs(rx - lx))
    if not cs:
        return None
    cx, cy = np.median([c[0] for c in cs]), np.median([c[1] for c in cs])
    side = int(min(W, H, round(np.median(ws) * FACE_TO_CROP)))
    x = int(min(max(cx - side / 2, 0), W - side)); y = int(min(max(cy - side / 2, 0), H - side))
    return f'{side}:{side}:{x}:{y}'


def measure(fm, crop_dir):
    rows = []
    for p in sorted(crop_dir.glob('f*.png')):
        P = landmarks(fm, cv2.imread(str(p)))
        if P is None:
            continue
        nose, lc, rc, top, chin = P(1), P(234), P(454), P(10), P(152)
        cx, fw = (lc[0] + rc[0]) / 2, abs(rc[0] - lc[0])
        cy, fh = (top[1] + chin[1]) / 2, abs(chin[1] - top[1])
        ear = lambda up, dn, a, b: abs(P(dn)[1] - P(up)[1]) / max(abs(P(b)[0] - P(a)[0]), 1)
        rows.append({'f': int(p.stem[1:]), 'hx': (nose[0] - cx) / fw, 'hy': (nose[1] - cy) / fh,
                     'eye': (ear(159, 145, 33, 133) + ear(386, 374, 362, 263)) / 2})
    return rows


def build_poses(rows):
    """朝向 = 鼻尖相对脸部轮廓中心的偏移，以第 0 帧（正脸）为原点，四个方向各自按最大转幅归一到 ±1。"""
    bx, by = rows[0]['hx'], rows[0]['hy']
    for r in rows:
        r['hx'] -= bx; r['hy'] -= by
    for key in ('hx', 'hy'):                       # 关键点逐帧有抖动，前后各 2 帧平均
        vals = [r[key] for r in rows]
        for i, r in enumerate(rows):
            w = vals[max(0, i - 2):i + 3]; r[key + '_s'] = sum(w) / len(w)
    # 眨眼候选 = 开合度低于前后 6 帧中位数的 85%（低头时眼睑整体下垂，不能用绝对阈值）
    eyes = [r['eye'] for r in rows]
    low = [i for i in range(len(rows))
           if eyes[i] < sorted(eyes[max(0, i - 6):i + 7])[len(eyes[max(0, i - 6):i + 7]) // 2] * 0.85]
    # 低头往下看时眼皮也会连续几帧垂下，那不是眨眼，剔掉就丢了「看正下方」的画面，绕圈还会跳几帧（10-20 实测）。
    # 真眨眼短促（≤ 5 帧，约 0.2 秒），而且头没有明显朝下：只剔这种。
    downs = sorted(r['hy_s'] for r in rows if r['hy_s'] > 0)
    down_ext = downs[int(len(downs) * .95)] if downs else 1
    runs = []
    for i in low:
        if runs and i - runs[-1][-1] <= 2:
            runs[-1].append(i)
        else:
            runs.append([i])
    blink = set()
    for run in runs:
        short = run[-1] - run[0] + 1 <= 5
        looking_down = max(rows[i]['hy_s'] for i in run) > 0.5 * down_ext
        if short and not looking_down:
            blink.update(rows[i]['f'] for i in run)
    keep = [r for r in rows if r['f'] not in blink]
    ext = lambda v: sorted(v)[int(len(v) * .95)] if v else 1
    xr = ext([r['hx_s'] for r in keep if r['hx_s'] > 0]); xl = ext([-r['hx_s'] for r in keep if r['hx_s'] < 0])
    # 上下幅度只看头基本朝前的帧：侧转时头会顺带上仰，混进来会把「正上方」压小
    mid = [r for r in keep if abs(r['hx_s']) < 0.3 * (xr if r['hx_s'] > 0 else xl)]
    yd = ext([r['hy_s'] for r in mid if r['hy_s'] > 0]); yu = ext([-r['hy_s'] for r in mid if r['hy_s'] < 0])
    poses = []
    for r in keep:
        x = r['hx_s'] / (xr if r['hx_s'] > 0 else xl); y = r['hy_s'] / (yd if r['hy_s'] > 0 else yu)
        poses.append([r['f'], round(max(-1.2, min(1.2, x)), 3), round(max(-1.2, min(1.2, y)), 3)])
    return poses, sorted(blink)


def build_ring(poses):
    """绕圈段：转幅到位后的帧按播放顺序排开，记屏幕方向角（0=右 90=下 180=左 270=上），平滑后强制单调递增。"""
    start = next((i for i, p in enumerate(poses) if math.hypot(p[1], p[2]) >= RING_MIN_R), None)
    if start is None:
        return []
    # 终点同样按转幅截：即梦首尾帧都是正脸，视频结尾头会收回正脸。视频刚好转一圈时不会触发 trim_ring，
    # 回正那几帧方向角还在「上」附近，混进环尾就会和环头的满幅仰头接在一起，转过接缝时跳（10-21 黑衣服视频 ×3.9）
    end = max(i for i, p in enumerate(poses) if math.hypot(p[1], p[2]) >= RING_MIN_R)
    seg, ang, prev = poses[start:end + 1], [], None
    for _, x, y in seg:
        a = math.degrees(math.atan2(y, x))
        if prev is not None:
            while a < prev - 180:
                a += 360
        ang.append(a); prev = a
    ang = [sum(ang[max(0, i - 3):i + 4]) / len(ang[max(0, i - 3):i + 4]) for i in range(len(ang))]
    for i in range(1, len(ang)):
        ang[i] = max(ang[i], ang[i - 1])
    return [[p[0], round(a, 2)] for p, a in zip(seg, ang)]


def _thumbs(crop_dir):
    cache = {}
    def get(f):
        if f not in cache:
            im = cv2.imread(str(crop_dir / f'f{f:03d}.png'), cv2.IMREAD_GRAYSCALE)
            cache[f] = cv2.resize(im, (96, 96), interpolation=cv2.INTER_AREA).astype(np.float32)
        return cache[f]
    return lambda a, b: float(np.mean(np.abs(get(a) - get(b))))


def trim_ring(ring, crop_dir):
    """视频转了不止一圈时裁成正好一圈。不裁的话同一方向在时间轴上出现两次，组件把首尾当成相接的环，
    鼠标越过起点时头会先多扫一段、再切回起点，转一圈到这里就跳。
    在所有跨度约 360° 的裁法 [i, j) 里，挑环尾 j-1 接回环头 i 时画面差最小的一种（这就是转过接缝时看到的变化），
    差不多时取帧数多的。"""
    if len(ring) < 3 or ring[-1][1] - ring[0][1] <= 360:
        return ring, None
    step = (ring[-1][1] - ring[0][1]) / (len(ring) - 1)
    diff = _thumbs(crop_dir)
    best = None
    for i in range(len(ring)):
        for j in range(i + 1, len(ring)):
            span = ring[j][1] - ring[i][1]
            if span < 360 - step:
                continue
            if span > 360 + step:
                break
            d = round(diff(ring[j - 1][0], ring[i][0]), 1)
            if best is None or (d, -(j - i)) < (best[0], -(best[2] - best[1])):
                best = (d, i, j)
    if best is None:
        return ring, None
    _, i, j = best
    return ring[i:j], {'start': ring[i][0], 'end': ring[j - 1][0], 'dropped_frames': len(ring) - (j - i)}


def fill_seam(ring, crop_dir, next_f):
    """环尾接回环头时缺的角度用光流补帧。视频没正好闭合时（比如头最后一段边转边收回正脸，满幅那一段没拍到），
    首尾两帧差好几帧的角度，转过接缝会跳。按缺口 ÷ 平均每帧角度补 n 帧：双向 DIS 光流先按运动对齐两端、再按时刻加权混合，
    比直接叠两张图少重影（10-21 黑衣服视频：缺口 23°，接缝 ×2.6 → 补 5 帧后每步 ×0.5 左右，和真实相邻帧一样）。
    补出的帧编号接在原视频最后一帧后面，写进 crop_dir，编码时一起进 avatar.mp4。缺口不到两帧的角度不补。"""
    step = (ring[-1][1] - ring[0][1]) / (len(ring) - 1)
    gap = ring[0][1] + 360 - ring[-1][1]
    n = round(gap / step) - 1
    if n < 1:
        return ring, None
    fa, fb = ring[-1][0], ring[0][0]
    a, b = (cv2.imread(str(crop_dir / f'f{f:03d}.png')) for f in (fa, fb))
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    ga, gb = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    f01, f10 = dis.calc(ga, gb, None), dis.calc(gb, ga, None)
    h, w = ga.shape
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    warp = lambda img, fl: cv2.remap(img, gx + fl[..., 0], gy + fl[..., 1], cv2.INTER_LINEAR,
                                     borderMode=cv2.BORDER_REPLICATE).astype(np.float32)
    added = []
    for k in range(1, n + 1):
        t = k / (n + 1)
        ft0 = -(1 - t) * t * f01 + t * t * f10          # t 时刻指向两端的流（Super SloMo 的线性近似）
        ft1 = (1 - t) ** 2 * f01 - t * (1 - t) * f10
        img = ((1 - t) * warp(a, ft0) + t * warp(b, ft1)).clip(0, 255).astype(np.uint8)
        f = next_f + k - 1
        cv2.imwrite(str(crop_dir / f'f{f:03d}.png'), img)
        added.append([f, round(ring[-1][1] + gap * t, 2)])
    return ring + added, {'frames': n, 'between': [fa, fb], 'gap_before_deg': round(gap, 1)}


def ring_smoothness(ring, crop_dir):
    """沿时间轴走一圈（含首尾接缝）相邻两帧的画面差，以中位数为 1。远大于 1 的地方转到那里会跳。"""
    diff = _thumbs(crop_dir)
    pairs = [(ring[k][0], ring[(k + 1) % len(ring)][0]) for k in range(len(ring))]
    ds = [diff(a, b) for a, b in pairs]
    med = sorted(ds)[len(ds) // 2] or 1
    jumps = [[a, b, round(d / med, 2)] for (a, b), d in zip(pairs, ds) if d > med * 2.5]
    return {'seam_vs_median': round(ds[-1] / med, 2), 'max_vs_median': round(max(ds) / med, 2), 'jumps': jumps}


def check_grid(ring, front, crop_dir, out):
    """九宫格：左上 上 右上 / 左 正脸 右 / 左下 下 右下，每格取方向角最接近的那一帧。"""
    dirs = [225, 270, 315, 180, None, 0, 135, 90, 45]
    def pick(deg):
        return min(ring, key=lambda r: abs((r[1] - deg + 180) % 360 - 180))[0]
    tiles = []
    for d in dirs:
        f = front if d is None else pick(d)
        im = cv2.resize(cv2.imread(str(crop_dir / f'f{f:03d}.png')), (240, 240))
        cv2.putText(im, f'#{f}', (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (60, 60, 220), 2)
        tiles.append(im)
    rows = [np.hstack(tiles[i:i + 3]) for i in (0, 3, 6)]
    cv2.imwrite(str(out), np.vstack(rows))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video'); ap.add_argument('--out', required=True)
    ap.add_argument('--crop', help='手动指定裁切 W:H:X:Y（像素），不给则按人脸自动算')
    ap.add_argument('--size', type=int, default=480)
    a = ap.parse_args()
    video, out = pathlib.Path(a.video).expanduser().resolve(), pathlib.Path(a.out).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    W, H, fps = probe(video)
    fm = mp.solutions.face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1, refine_landmarks=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp); src, crop_dir = tmp / 'src', tmp / 'crop'
        src.mkdir(); crop_dir.mkdir()
        crop = a.crop
        if not crop:
            sh('ffmpeg', '-v', 'error', '-i', str(video), '-start_number', '0', str(src / 'f%03d.png'))
            crop = auto_crop(fm, src, W, H)
            if crop is None:
                sys.exit('整段视频都识别不到人脸：检查视频里是不是正常的人脸，或用 --crop 手动指定')
        sh('ffmpeg', '-v', 'error', '-i', str(video), '-vf', f'crop={crop}', '-start_number', '0', str(crop_dir / 'f%03d.png'))
        n_all = len(list(crop_dir.glob('f*.png')))
        rows = measure(fm, crop_dir)
        problems = []
        if len(rows) < n_all * MIN_DETECT:
            problems.append(f'人脸识别率 {len(rows)}/{n_all} 低于 {MIN_DETECT:.0%}：脸转得太偏或被遮挡')
        if not rows or rows[0]['f'] != 0:
            sys.exit('第 0 帧识别不到人脸：视频应从正脸开始（即梦首帧用正脸图）')
        poses, blink = build_poses(rows)
        ring = build_ring(poses)
        ring, trimmed = trim_ring(ring, crop_dir)
        gap = (ring[0][1] + 360 - ring[-1][1]) if len(ring) > 1 else 360   # 补帧前的缺口：判断视频转没转满一圈看它
        seg = [ring[0][0], ring[-1][0]] if ring else None
        seam_fill = None
        if len(ring) >= 30 and gap <= MAX_GAP_DEG:
            ring, seam_fill = fill_seam(ring, crop_dir, n_all)
        smooth = ring_smoothness(ring, crop_dir) if len(ring) > 2 else None
        if len(ring) < 30:
            problems.append(f'绕圈段只有 {len(ring)} 帧：头转动幅度太小，或只在左右摆没有上下')
        elif gap > MAX_GAP_DEG:
            problems.append(f'绕圈缺口 {gap:.0f}°（上限 {MAX_GAP_DEG}°）：头没转满一圈')
        if smooth and smooth['jumps']:
            problems.append('绕圈段有画面跳变（帧对与倍数：' + '，'.join(f'{a}→{b} ×{r}' for a, b, r in smooth['jumps'])
                            + '）：转到那里会跳，多半是视频那几帧走样，建议重新生成')

        cv2.imwrite(str(out / 'poster.webp'), cv2.resize(cv2.imread(str(crop_dir / 'f000.png')), (a.size, a.size),
                    interpolation=cv2.INTER_AREA), [cv2.IMWRITE_WEBP_QUALITY, 82])
        if ring:
            check_grid(ring, poses[0][0], crop_dir, out / 'check.png')
        if seam_fill:
            # 补出来的帧原视频里没有：从裁好的帧序列（原帧 + 补帧）编码
            sh('ffmpeg', '-v', 'error', '-y', '-framerate', str(fps), '-start_number', '0', '-i', str(crop_dir / 'f%03d.png'),
               '-vf', f'scale={a.size}:{a.size}', *X264, str(out / 'avatar.mp4'))

    if not seam_fill:
        sh('ffmpeg', '-v', 'error', '-y', '-i', str(video), '-an', '-vf', f'crop={crop},scale={a.size}:{a.size}',
           *X264, str(out / 'avatar.mp4'))
    data ={'size': a.size, 'fps': fps, 'front': poses[0][0], 'poses': poses, 'ring': ring}
    (out / 'poses.js').write_text(
        '// avatar-look/scripts/process_video.py 产出，勿手改。poses: [帧号, x 右正左负, y 下正上负]；\n'
        '// ring: [帧号, 屏幕方向角 0=右 90=下 180=左 270=上]，头绕圈那段按播放顺序排列，角度单调递增\n'
        'window.AVATAR_LOOK_DATA = ' + json.dumps(data, separators=(',', ':')) + ';\n', encoding='utf-8')

    report = {'video': str(video), 'frames': n_all, 'fps': fps, 'crop': crop, 'detected': len(rows),
              'blink_frames': blink, 'ring': seg, 'ring_frames': len(ring),
              'gap_deg': round(gap, 1), 'trimmed': trimmed, 'seam_fill': seam_fill, 'smoothness': smooth, 'mp4_kb': round((out / 'avatar.mp4').stat().st_size / 1024),
              'ok': not problems, 'problems': problems}
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'裁切 {crop}；人脸识别 {len(rows)}/{n_all}；剔除眨眼帧 {blink}（这些帧不进时间轴，请对照视频确认是真眨眼）')
    if ring:
        print(f'绕圈段 第 {seg[0]}—{seg[1]} 帧，{ring[0][1]:.0f}° 起，缺口 {gap:.0f}°')
        if seam_fill:
            print(f'首尾缺口用光流补了 {seam_fill["frames"]} 帧（第 {seg[1]} 帧 → 第 {seg[0]} 帧之间，编号接在视频末尾），时间轴共 {len(ring)} 帧')
        if trimmed:
            print(f'视频转了不止一圈，已裁成一圈：去掉 {trimmed["dropped_frames"]} 帧，环从第 {trimmed["start"]} 帧到第 {trimmed["end"]} 帧，接缝 {trimmed["end"]} → {trimmed["start"]}')
        if smooth:
            print(f'连贯度（相邻帧画面差，中位数为 1）：接缝 ×{smooth["seam_vs_median"]}，最大 ×{smooth["max_vs_median"]}')
    print(f'avatar.mp4 {report["mp4_kb"]} KB；核对图 {out / "check.png"}')
    if problems:
        print('自检不通过，建议重新生成视频：\n  - ' + '\n  - '.join(problems))
        sys.exit(2)
    print('自检通过')


if __name__ == '__main__':
    main()
