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
    # 眨眼 = 开合度低于前后 6 帧中位数的 85%（低头时眼睑整体下垂，不能用绝对阈值）
    eyes = [r['eye'] for r in rows]
    blink = {rows[i]['f'] for i in range(len(rows))
             if eyes[i] < sorted(eyes[max(0, i - 6):i + 7])[len(eyes[max(0, i - 6):i + 7]) // 2] * 0.85}
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
    seg, ang, prev = poses[start:], [], None
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
        gap = (ring[0][1] + 360 - ring[-1][1]) if len(ring) > 1 else 360
        if len(ring) < 30:
            problems.append(f'绕圈段只有 {len(ring)} 帧：头转动幅度太小，或只在左右摆没有上下')
        elif gap > MAX_GAP_DEG:
            problems.append(f'绕圈缺口 {gap:.0f}°（上限 {MAX_GAP_DEG}°）：头没转满一圈')

        cv2.imwrite(str(out / 'poster.webp'), cv2.resize(cv2.imread(str(crop_dir / 'f000.png')), (a.size, a.size),
                    interpolation=cv2.INTER_AREA), [cv2.IMWRITE_WEBP_QUALITY, 82])
        if ring:
            check_grid(ring, poses[0][0], crop_dir, out / 'check.png')

    sh('ffmpeg', '-v', 'error', '-y', '-i', str(video), '-an', '-vf', f'crop={crop},scale={a.size}:{a.size}',
       '-c:v', 'libx264', '-preset', 'slow', '-crf', '22', '-g', '1', '-pix_fmt', 'yuv420p',
       '-movflags', '+faststart', str(out / 'avatar.mp4'))
    data = {'size': a.size, 'fps': fps, 'front': poses[0][0], 'poses': poses, 'ring': ring}
    (out / 'poses.js').write_text(
        '// avatar-look/scripts/process_video.py 产出，勿手改。poses: [帧号, x 右正左负, y 下正上负]；\n'
        '// ring: [帧号, 屏幕方向角 0=右 90=下 180=左 270=上]，头绕圈那段按播放顺序排列，角度单调递增\n'
        'window.AVATAR_LOOK_DATA = ' + json.dumps(data, separators=(',', ':')) + ';\n', encoding='utf-8')

    report = {'video': str(video), 'frames': n_all, 'fps': fps, 'crop': crop, 'detected': len(rows),
              'blink_frames': blink, 'ring': [ring[0][0], ring[-1][0]] if ring else None, 'ring_frames': len(ring),
              'gap_deg': round(gap, 1), 'mp4_kb': round((out / 'avatar.mp4').stat().st_size / 1024),
              'ok': not problems, 'problems': problems}
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'裁切 {crop}；人脸识别 {len(rows)}/{n_all}；剔除眨眼帧 {blink}（不进绕圈段，请对照视频确认）')
    if ring:
        print(f'绕圈段 第 {ring[0][0]}—{ring[-1][0]} 帧共 {len(ring)} 帧，{ring[0][1]:.0f}° → {ring[-1][1]:.0f}°，缺口 {gap:.0f}°')
    print(f'avatar.mp4 {report["mp4_kb"]} KB；核对图 {out / "check.png"}')
    if problems:
        print('自检不通过，建议重新生成视频：\n  - ' + '\n  - '.join(problems))
        sys.exit(2)
    print('自检通过')


if __name__ == '__main__':
    main()
