/* avatar-look.js — 3D 头像看向鼠标
 *
 * 素材是「头绕一圈」的形象视频（avatar-look skill 的 scripts/process_video.py 产出 avatar.mp4，每帧都是关键帧），
 * poses.js 的 ring 是绕圈那段的帧和各自的屏幕方向角。
 * 把 ring 当成一条首尾相接的时间轴：鼠标相对头像中心的方向 → 时间轴上的目标位置；
 * 播放头按最短路径追过去，每走到新的一帧就让视频跳到那一帧。
 * 跳转用 seeked 串联：上一次没跳完时只记下最新目标，等 seeked 事件再跳，浏览器不会丢弃中途的跳转。
 * 只算相对头像中心的方向，头像放在页面哪里、显示多大都不用改。
 *
 * 用法：先引 poses.js 再引本文件，然后
 *   <div data-avatar-look><img src=".../poster.webp" alt=""></div>   自动挂载（容器要有宽高）
 *   AvatarLook.mount(el)    手动挂载；容器是 JS 渲染出来的就在渲染后调 AvatarLook.scan()
 * 页面加载时显示正脸（poster.webp）；鼠标离开窗口一会儿后淡回正脸。
 * 触屏只在手指按住时跟随；prefers-reduced-motion 时只显示正脸，不加载视频。
 */
(function () {
  'use strict';
  var D = window.AVATAR_LOOK_DATA;
  if (!D || !D.ring) { console.warn('avatar-look: 先引入 poses.js（需含 ring）'); return; }

  var BASE = (document.currentScript && document.currentScript.src || '').replace(/[^/]*$/, '');
  var TAU_MS = 90;        // 播放头追目标的时间常数：越大转得越"沉"
  var MAX_SPEED = 170;    // 播放头最快每秒走多少帧（一圈约 110 帧）
  var FACE_FADE_MS = 260; // 正脸与视频之间的淡入淡出
  var IDLE_MS = 1500;     // 鼠标离开多久后回正脸
  var FPS = D.fps || 24;

  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---- 时间轴：位置 0..n-1 对应 ring 的每一帧；n-1 到 L 是首尾之间没拍到的一段，过中点切换首尾帧 ----
  var R = D.ring, n = R.length;
  var stepDeg = (R[n - 1][1] - R[0][1]) / (n - 1);
  var GAP = Math.max(1, (R[0][1] + 360 - R[n - 1][1]) / stepDeg);
  var L = n - 1 + GAP;
  var KP = [], KA = [];                       // 角度 → 位置 的分段线性节点
  for (var i = 0; i < n; i++) { KP.push(i); KA.push(R[i][1]); }
  KP.push(L); KA.push(R[0][1] + 360);

  function posFromAngle(deg) {
    var a = deg;
    while (a < KA[0]) a += 360;
    while (a >= KA[0] + 360) a -= 360;
    for (var k = 0; k < KA.length - 1; k++) {
      if (a < KA[k + 1]) {
        var span = KA[k + 1] - KA[k];
        return KP[k] + (span > 0 ? (a - KA[k]) / span : 0) * (KP[k + 1] - KP[k]);
      }
    }
    return 0;
  }
  function frameAt(p) {                       // 位置 → 视频帧号
    p = ((p % L) + L) % L;
    if (p <= n - 1) return R[Math.round(p)][0];
    return (p - (n - 1)) / GAP < 0.5 ? R[n - 1][0] : R[0][0];
  }
  function wrapDiff(d) { d = ((d % L) + L) % L; return d > L / 2 ? d - L : d; }

  // ---- 指针：鼠标 / 触控笔随时跟随；触屏只在按住时跟随 ----
  var pointer = null, lastSeen = 0;
  function setP(e) { pointer = { x: e.clientX, y: e.clientY }; lastSeen = performance.now(); }
  addEventListener('pointermove', function (e) { if (e.pointerType !== 'touch' || e.buttons) setP(e); }, { passive: true });
  addEventListener('pointerdown', setP, { passive: true });
  addEventListener('pointerup', function (e) { if (e.pointerType === 'touch') pointer = null; });
  addEventListener('pointercancel', function () { pointer = null; });
  document.addEventListener('mouseleave', function () { pointer = null; });
  addEventListener('blur', function () { pointer = null; });

  // ---- seeked 串联 ----
  function seekTo(it, t) {
    if (it.seeking) { it.pending = t; return; }
    if (Math.abs(it.v.currentTime - t) < 0.001) return;
    it.seeking = true; it.v.currentTime = t;
  }
  function onSeeked(it) {
    it.seeking = false; it.shown = true;
    if (it.pending !== null) { var t = it.pending; it.pending = null; seekTo(it, t); }
  }

  var insts = [];
  function mount(el) {
    if (el.__avatarLook) return el.__avatarLook;
    if (getComputedStyle(el).position === 'static') el.style.position = 'relative';
    if (!el.querySelector('img')) {
      var im = document.createElement('img');
      im.src = BASE + 'poster.webp'; im.alt = '';
      im.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;display:block;object-fit:cover;';
      el.appendChild(im);
    }
    var it = { el: el, v: null, ready: false, p: 0, target: null, frame: -1,
               seeking: false, pending: null, shown: false, faceOn: true };
    if (!reduce) {
      var v = document.createElement('video');
      v.muted = true; v.defaultMuted = true; v.playsInline = true; v.preload = 'auto';
      v.disablePictureInPicture = true;
      v.setAttribute('muted', ''); v.setAttribute('playsinline', ''); v.setAttribute('aria-hidden', 'true');
      v.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;display:block;object-fit:cover;' +
        'opacity:0;transition:opacity ' + FACE_FADE_MS + 'ms ease;pointer-events:none;';
      v.addEventListener('seeked', function () { onSeeked(it); });
      v.addEventListener('loadeddata', function () { it.ready = true; });
      // iOS Safari 不播放就可能不解码画面：静音视频允许自动播放，播一下立刻暂停
      v.addEventListener('loadedmetadata', function () {
        if (v.readyState < 2) { var pr = v.play(); if (pr && pr.then) pr.then(function () { v.pause(); }, function () {}); }
      });
      v.src = BASE + 'avatar.mp4';
      el.appendChild(v);
      it.v = v;
    }
    insts.push(it);
    el.__avatarLook = it;
    return it;
  }

  var last = 0;
  function tick(now) {
    var dt = Math.min(50, now - (last || now)); last = now;
    var vh = innerHeight, vw = innerWidth;
    for (var i = 0; i < insts.length; i++) {
      var it = insts[i];
      if (!it.v || !it.ready) continue;
      var r = it.el.getBoundingClientRect();
      if (r.width === 0 || r.bottom < 0 || r.top > vh || r.right < 0 || r.left > vw) continue;

      if (pointer) {
        var dx = pointer.x - (r.left + r.width / 2), dy = pointer.y - (r.top + r.height / 2);
        // 鼠标在头像中心附近时方向不稳，保持上一次的目标
        if (Math.hypot(dx, dy) > r.width * 0.3) {
          var tp = posFromAngle(Math.atan2(dy, dx) * 180 / Math.PI);
          if (it.target === null) it.p = tp;     // 第一次：直接从正脸淡到该方向
          it.target = tp;
        }
      }
      if (it.target !== null) {
        var d = wrapDiff(it.target - it.p);
        var step = d * (1 - Math.exp(-dt / TAU_MS)), cap = MAX_SPEED * dt / 1000;
        it.p = (((it.p + Math.max(-cap, Math.min(cap, step))) % L) + L) % L;
        var f = frameAt(it.p);
        if (f !== it.frame) { it.frame = f; seekTo(it, (f + 0.5) / FPS); }
      }
      // 视频跳到位之前、或鼠标离开一会儿后，显示正脸
      var faceOn = !it.shown || it.target === null || (!pointer && now - lastSeen > IDLE_MS);
      if (faceOn !== it.faceOn) { it.faceOn = faceOn; it.v.style.opacity = faceOn ? '0' : '1'; }
    }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);

  function scan() {
    var els = document.querySelectorAll('[data-avatar-look]');
    for (var i = 0; i < els.length; i++) mount(els[i]);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', scan);
  else scan();

  window.AvatarLook = {
    mount: mount, scan: scan,
    poster: BASE + 'poster.webp',               // 正脸图，可作 <img> 占位或其他地方的静态头像
    model: { ring: R, L: L, posFromAngle: posFromAngle, frameAt: frameAt },
    _state: { insts: insts, ready: function () { return insts.every(function (it) { return !it.v || it.ready; }); } }
  };
})();
