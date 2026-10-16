# -*- coding: utf-8 -*-
"""puppet_engine.py —— 程序化「分层定格动画」引擎（不依赖任何 AI）

思路：把正面立绘 front_stand.png 放大到 2 倍作为母版，按颜色/位置自动分出
  头(含发) / 长发 / 披风下摆 / 手臂 / 下半身 等区域，用位移场（scipy map_coordinates）
  对每个区域施加呼吸、点头、挥手、跳跃、摇摆、颤抖、走路…等运动基元，
  再叠上程序化特效（气泡/星星/爱心/汗滴/音符/烟花/硬币/花瓣/雨/Zzz 等），
  输出与提示词强制约束一致的 10 秒纯绿幕 mp4：1280x720 / 24fps / 头顶 20% / 脚底 85% / 居中 / 首尾帧一致。

用法：
  python tools/puppet_engine.py --list                 # 打印 106 个动作 → 运动程序映射表
  python tools/puppet_engine.py --only 待机呼吸休闲 点击回应-开心跃动
  python tools/puppet_engine.py --all --jobs 8         # 并行渲染全部动作到 video/
  python tools/puppet_engine.py --all --limit 3        # 只渲染前 3 个（试跑）
  python tools/puppet_engine.py --report report/motion_map.md
"""
from __future__ import annotations

import argparse
import math
import os
import re
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter, map_coordinates

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
FFMPEG = ROOT / ".tools" / "ffmpeg-9.0.1-essentials_build" / "bin" / "ffmpeg.exe"
FIG_PATH = ROOT / "character" / "front_stand.png"
OUT_DIR = ROOT / "video"
PROMPT_DIR = ROOT / "jimeng-prompts"

W, H, FPS, DUR = 1280, 720, 24, 10.0
N_FRAMES = int(FPS * DUR)
GREEN = np.array([0, 255, 0], np.float32)
HEAD_LINE = int(H * 0.20)      # 144
FEET_LINE = int(H * 0.85)      # 612
CX = W // 2
SS = 2                          # 母版超采样倍数

# ---------------------------------------------------------------- 母版与区域
class Figure:
    def __init__(self, path: Path = FIG_PATH):
        im = Image.open(path).convert("RGBA")
        a = np.asarray(im).astype(np.float32)
        a[..., 3] = np.where(a[..., 3] >= 200, 255.0, a[..., 3])
        self.w, self.h = im.size
        self.rgb = a[..., :3].astype(np.float32)
        self.alpha = a[..., 3]
        # 放大母版（LANCZOS）
        self.big = np.dstack([self.rgb, self.alpha]).astype(np.uint8)
        self.big = np.asarray(Image.fromarray(self.big, "RGBA").resize((self.w * SS, self.h * SS), Image.LANCZOS)).astype(np.float32)
        self.BH, self.BW = self.big.shape[:2]
        self._build_masks()
        self._build_grids()

    # ---- 颜色分区的原始掩码（1x 坐标）
    def _build_masks(self):
        R, G, B = self.rgb[..., 0], self.rgb[..., 1], self.rgb[..., 2]
        lum = 0.299 * R + 0.587 * G + 0.114 * B
        mx = self.rgb.max(2); mn = self.rgb.min(2); sat = mx - mn
        op = self.alpha > 128
        skin = op & (R > 232) & (G > 198) & (G < 250) & (B > 172) & (B < 242)
        eye = op & (B > 165) & (B > R - 40) & (G < 185)
        dark = op & (lum < 95)
        bright = op & (lum > 198) & (sat < 32)

        # 脸部行（最上面连续一段皮肤行）→ 颈部位置
        rows = skin.sum(1)
        idx = np.where(rows > 2)[0]
        self.face_top, self.face_bot = (int(idx[0]), int(idx[-1])) if len(idx) else (int(0.18 * self.h), int(0.42 * self.h))
        grp = [int(idx[0])]
        for v in idx[1:]:
            if v - grp[-1] <= 8:
                grp.append(int(v))
            else:
                break
        self.face_top, self.face_bot = grp[0], grp[-1]
        self.neck_y = min(self.h - 2, self.face_bot + 3)
        self.face_cx = int(np.argmax(skin[self.face_top:self.face_bot + 1].sum(0))) if len(idx) else self.w // 2

        # 手臂：躯干带的左右外突
        y0, y1 = self.neck_y, int(0.80 * self.h)
        band = op[y0:y1]
        colcov = band.mean(0)
        core = np.where(colcov > 0.70)[0]
        arm = np.zeros_like(op, bool)
        if len(core):
            cl, cr = int(core[0]), int(core[-1])
            sub = op[y0:y1]
            cols = np.arange(self.w)[None, :]
            arm[y0:y1] = sub & ((cols < cl + 3) | (cols > cr - 3))
        self.masks1 = {
            "op": op.astype(np.float32),
            "skin": skin.astype(np.float32),
            "eye": eye.astype(np.float32),
            "dark": dark.astype(np.float32),
            "bright": bright.astype(np.float32),
            "arm": arm.astype(np.float32),
        }

    # ---- 2x 位移场用的网格与权重
    def _build_grids(self):
        yy, xx = np.mgrid[0:self.BH, 0:self.BW].astype(np.float32)
        self.Y, self.X = yy, xx
        self.s = float((FEET_LINE - HEAD_LINE) / self.h)      # 1x 缩放比
        m = {k: np.asarray(Image.fromarray((v * 255).astype(np.uint8), "L").resize((self.BW, self.BH), Image.BILINEAR)).astype(np.float32) / 255.0
             for k, v in self.masks1.items()}
        sm = lambda z, s: gaussian_filter(z, s)
        head = np.clip(1.0 - (yy / SS - self.neck_y) / 8.0, 0, 1) * m["op"]
        head = np.where(yy / SS <= self.neck_y, m["op"], 0.0).astype(np.float32)
        hair = m["bright"] * np.clip(1.0 - (yy / SS) / (0.72 * self.h), 0, 1)
        cape = np.where((yy / SS > self.neck_y) & (yy / SS < 0.90 * self.h), m["dark"], 0.0).astype(np.float32)
        cape = cape * np.clip((yy / SS - self.neck_y) / (0.35 * self.h), 0, 1)
        lower = np.where(yy / SS > 0.74 * self.h, m["op"], 0.0).astype(np.float32)
        self.reg = {
            "op": sm(m["op"], 2.0),
            "head": sm(head, 2.0),
            "hair": sm(hair, 3.0),
            "cape": sm(cape, 3.0),
            "arm": sm(m["arm"], 2.5),
            "lower": sm(lower, 2.0),
            "eye": m["eye"],
        }
        self.neck_pivot = (self.face_cx * SS, (self.neck_y + 2) * SS)
        self.foot_pivot = (self.face_cx * SS, (self.h - 1) * SS)

    # ---- 采样（含位移场）
    def sample(self, dy, dx):
        ys = self.Y + dy
        xs = self.X + dx
        out = np.empty((self.BH, self.BW, 4), np.float32)
        arr = self.big
        for c in range(4):
            out[..., c] = map_coordinates(arr[..., c], [ys, xs], order=1, mode="constant", cval=0.0, prefilter=False)
        return out

    def to_canvas(self, warped, extra_scale=1.0):
        """把 2x 母版缩到最终尺寸并贴到绿幕上（脚底锚点）。"""
        fw = max(1, int(self.w * self.s * extra_scale))
        fh = max(1, int(self.h * self.s * extra_scale))
        small = Image.fromarray(warped.astype(np.uint8), "RGBA").resize((fw, fh), Image.LANCZOS)
        ar = np.asarray(small).astype(np.float32)
        alpha = (ar[..., 3:4] / 255.0)
        canvas = np.empty((H, W, 3), np.float32)
        canvas[:] = GREEN
        x0 = CX - fw // 2
        y0 = FEET_LINE - fh
        if x0 < 0:
            ar = ar[:, -x0:]; alpha = alpha[:, -x0:]; x0 = 0
        if y0 < 0:
            ar = ar[-y0:]; alpha = alpha[-y0:]; y0 = 0
        hh = min(fh, H - y0); ww = min(fw, W - x0)
        region = canvas[y0:y0 + hh, x0:x0 + ww]
        canvas[y0:y0 + hh, x0:x0 + ww] = ar[:hh, :ww, :3] * alpha[:hh, :ww] + GREEN * (1 - alpha[:hh, :ww])
        return canvas


# ---------------------------------------------------------------- 运动基元
def _rot(px, py, deg, X, Y):
    th = math.radians(deg)
    c, s = math.cos(th) - 1.0, math.sin(th)
    dx = (X - px) * c - (Y - py) * s
    dy = (X - px) * s + (Y - py) * c
    return dy, dx


def fields(t, prog, fig: Figure, dur=DUR):
    """返回 2x 网格上的 (dy, dx)。prog = {'prims': [...], 'effects': [...]}"""
    Y, X, Wt = fig.Y, fig.X, fig.reg
    zero = np.zeros_like(Y)
    dy, dx = zero.copy(), zero.copy()

    def T(period, phase=0.0):
        """周期化相位；保证 t=0 与 t=dur 同相（周期取 dur 的整数分之一）。"""
        cycles = max(1, round(dur / period))
        return 2 * math.pi * cycles * (t / dur) + phase

    for p in prog.get("prims", []):
        k, o = p[0], (p[1] if len(p) > 1 else {})
        w = Wt.get(o.get("region", "op"), Wt["op"])
        if k == "breath":
            a = o.get("amp", 0.014) * math.sin(T(o.get("period", 3.333)))
            fdy, fdx = _rot(*fig.foot_pivot, 0, X, Y)
            dy += (-(Y - fig.foot_pivot[1]) * a) * w
            dx += (-(X - fig.foot_pivot[0]) * a * 0.5) * w
        elif k == "bob":
            dy += (o.get("amp", 8.0) * SS * math.sin(T(o.get("period", 3.0)))) * w
        elif k == "lean":
            dgy, dgx = _rot(*fig.foot_pivot, o.get("deg", 3.0) * math.sin(T(o.get("period", 4.0))), X, Y)
            dy += dgy * w; dx += dgx * w
        elif k in ("nod", "tilt"):
            deg = o.get("deg", 6.0) * math.sin(T(o.get("period", 2.0)))
            piv = (fig.neck_pivot[0], fig.neck_pivot[1] + o.get("pivot_dy", 0) * SS)
            if k == "tilt":
                dgy, dgx = _rot(piv[0], piv[1], deg, X, Y)
            else:   # nod = 绕颈部前后倾（用垂直压缩近似俯仰）
                u = (Y - piv[1]) / (300 * SS)
                dgy = -np.abs(u) * deg * 3.0 * SS; dgx = np.zeros_like(X)
            dy += dgy * w; dx += dgx * w
        elif k == "sway":
            ph = T(o.get("period", 5.0), -o.get("lag", 0.7))
            amp = o.get("amp", 4.0) * SS
            depth = np.clip((fig.h * SS - Y) / (fig.h * SS), 0, 1)
            dx += (amp * math.sin(ph) * depth) * w
        elif k == "hair":
            ph = T(o.get("period", 4.0), -o.get("lag", 0.9))
            amp = o.get("amp", 6.0) * SS
            dx += (amp * math.sin(ph)) * w
            dy += (0.25 * amp * math.cos(ph)) * w
        elif k == "arm":
            side = o.get("side", 1)
            amp = o.get("deg", 22.0) * math.sin(T(o.get("period", 1.2)))
            piv = (fig.neck_pivot[0] + side * 60 * SS, fig.neck_pivot[1] + 30 * SS)
            dgy, dgx = _rot(piv[0], piv[1], side * abs(amp) if o.get("up", True) else amp, X, Y)
            dy += dgy * w; dx += dgx * w
        elif k == "walk":
            ph = T(o.get("period", 1.0))
            dy += (o.get("amp", 10.0) * SS * np.abs(np.sin(ph))) * w
            dx += (2.0 * SS * math.sin(ph)) * w
        elif k == "hop":
            for (t0, hd, hmax) in o.get("hops", [(1.0, 0.5, 60)]):
                if t0 - 0.12 <= t < t0:
                    u = (t - (t0 - 0.12)) / 0.12
                    dy += (-8.0 * SS * u) * w
                elif t0 <= t < t0 + hd:
                    u = (t - t0) / hd
                    dy += (-4 * hmax * SS * u * (1 - u)) * w
                elif t0 + hd <= t < t0 + hd + 0.15:
                    u = 1 - (t - t0 - hd) / 0.15
                    dy += (-6.0 * SS * u) * w
        elif k == "shake":
            deg = o.get("deg", 2.2) * math.sin(2 * math.pi * o.get("freq", 6.0) * t)
            dgy, dgx = _rot(*fig.foot_pivot, deg, X, Y)
            dy += dgy * w; dx += dgx * w
        elif k == "stretch":
            a = o.get("amp", 0.05) * (0.5 - 0.5 * math.cos(T(o.get("period", 6.0))))
            dy += (-(Y - fig.foot_pivot[1]) * a) * w
            dx += ((X - fig.foot_pivot[0]) * a * 0.35) * w
        elif k == "bow":
            a = o.get("amp", 0.10) * (0.5 - 0.5 * math.cos(T(o.get("period", 6.0))))
            dy += ((Y - fig.foot_pivot[1]) * a) * w * 0.8
            dx += (-(X - fig.neck_pivot[0]) * a * 0.4) * w
        elif k == "shift":
            dx += (o.get("amp", 5.0) * SS * math.sin(T(o.get("period", 4.0)))) * w
        elif k == "crouch":
            a = o.get("amp", 0.10) * (0.5 - 0.5 * math.cos(T(o.get("period", 5.0))))
            dy += ((Y - fig.foot_pivot[1]) * a) * w
            dx += (-(X - fig.foot_pivot[0]) * a * 0.3) * w
        elif k == "leg":
            ph = T(o.get("period", 1.0))
            dy += (-o.get("amp", 16.0) * SS * max(0.0, math.sin(ph)) ** 2) * w
    return dy, dx


# ---------------------------------------------------------------- 特效（画在最终画布上）
class Effects:
    """程序化特效；全部用确定性随机（种子固定），保证可复现。"""

    def __init__(self, fig: Figure):
        self.fig = fig
        face_x = CX + (fig.face_cx - fig.w / 2) * fig.s
        face_y = FEET_LINE - (fig.h - fig.face_bot) * fig.s
        self.face = (face_x, face_y)
        self.rng = np.random.RandomState(20261016)

    def _particles(self, d, t, kind, n, area, size, color, spread=1.0):
        x0, x1, y0, y1 = area
        for i in range(n):
            ph = (t / DUR + i / n) % 1.0
            py = y1 - ph * (y1 - y0) * spread
            px = x0 + (x1 - x0) * ((i * 0.6180339887) % 1.0) + math.sin(t * 2 + i) * 8
            a = int(230 * min(1.0, 3 * ph) * min(1.0, 3 * (1 - ph)) + 20)
            s = size * (0.7 + 0.5 * ((i % 3) / 2))
            if kind == "bubble":
                d.ellipse([px - s, py - s, px + s, py + s], outline=color + (a,), width=3)
                d.ellipse([px - s * 0.4, py - s * 0.5, px - s * 0.1, py - s * 0.2], fill=(255, 255, 255, a))
            elif kind == "heart":
                for dx2, dy2 in [(-s * .6, 0), (s * .6, 0)]:
                    d.ellipse([px + dx2 - s * .6, py + dy2 - s * .6, px + dx2 + s * .6, py + dy2 + s * .6], fill=color + (a,))
                d.polygon([(px - s * 1.2, py + s * .2), (px + s * 1.2, py + s * .2), (px, py + s * 1.7)], fill=color + (a,))
            elif kind == "star":
                pts = []
                for k in range(10):
                    r = s if k % 2 == 0 else s * 0.42
                    ang = -math.pi / 2 + k * math.pi / 5
                    pts.append((px + r * math.cos(ang), py + r * math.sin(ang)))
                d.polygon(pts, fill=color + (a,))
            elif kind == "note":
                d.ellipse([px - s * .7, py - s * .5, px + s * .5, py + s * .7], fill=color + (a,))
                d.line([(px + s * .45, py + s * .1), (px + s * .45, py - s * 1.6)], fill=color + (a,), width=3)
            elif kind == "sweat":
                d.polygon([(px, py - s), (px + s * .7, py + s * .6), (px - s * .7, py + s * .6)], fill=color + (a,))
            elif kind == "petal":
                d.ellipse([px - s, py - s * .5, px + s, py + s * .5], fill=color + (a,))
            elif kind == "coin":
                d.ellipse([px - s, py - s * .6, px + s, py + s * .6], fill=color + (a,), outline=(190, 140, 40, a), width=2)
            elif kind == "spark":
                d.line([(px - s, py), (px + s, py)], fill=color + (a,), width=3)
                d.line([(px, py - s), (px, py + s)], fill=color + (a,), width=3)
            elif kind == "rain":
                d.line([(px, py), (px - 3, py + s * 2)], fill=color + (a,), width=2)

    def draw(self, frame, t, kinds):
        if not kinds:
            return frame
        img = Image.fromarray(frame.astype(np.uint8), "RGB").convert("RGBA")
        d = ImageDraw.Draw(img, "RGBA")
        for k in kinds:
            kind = k[0]
            o = k[1] if len(k) > 1 else {}
            if kind == "zzz":
                for i in range(3):
                    ph = (t / 3.0 + i / 3.0) % 1.0
                    s = 22 + 10 * i
                    x = self.face[0] + 90 + ph * 60 + i * 30
                    y = self.face[1] - 60 - ph * 120 - i * 20
                    d.text((x, y), "Z", fill=(120, 170, 255, 230), stroke_width=2, stroke_fill=(255, 255, 255, 230))
            elif kind == "bang":
                x, y = self.face[0] + 120, self.face[1] - 120
                d.line([(x, y - 34), (x, y + 6)], fill=(255, 90, 90, 240), width=9)
                d.ellipse([x - 5, y + 14, x + 5, y + 24], fill=(255, 90, 90, 240))
            elif kind == "question":
                d.text((self.face[0] + 110, self.face[1] - 150), "?", fill=(120, 200, 255, 235), stroke_width=3, stroke_fill=(255, 255, 255, 235))
            elif kind == "anger":
                for i in range(2):
                    x = self.face[0] + 95 + i * 26
                    d.line([(x, self.face[1] - 150), (x + 18, self.face[1] - 132)], fill=(255, 80, 80, 240), width=6)
                    d.line([(x + 18, self.face[1] - 150), (x, self.face[1] - 132)], fill=(255, 80, 80, 240), width=6)
            elif kind == "blush":
                for sx in (-1, 1):
                    x = self.face[0] + sx * 46; y = self.face[1] + 6
                    d.ellipse([x - 20, y - 11, x + 20, y + 11], fill=(255, 150, 170, o.get("alpha", 110)))
            elif kind == "tear":
                for sx in (-1, 1):
                    x = self.face[0] + sx * 34; y = self.face[1] + 10
                    ph = math.sin(t * 4 + sx) * 4
                    d.ellipse([x - 6 + ph, y, x + 6 + ph, y + 26], fill=(140, 200, 255, 220))
            elif kind == "firework":
                cx2, cy2 = o.get("center", (W * 0.5, H * 0.34))
                for burst in range(3):
                    tt = (t / DUR * 3 + burst / 3.0) % 1.0
                    if tt > 0.75:
                        continue
                    rad = 40 + 210 * tt
                    a = int(240 * (1 - tt / 0.75))
                    col = [(255, 210, 90), (255, 130, 170), (140, 220, 255)][burst]
                    for i in range(14):
                        ang = i * 2 * math.pi / 14 + burst
                        px = cx2 + rad * math.cos(ang); py = cy2 + rad * math.sin(ang) * 0.7
                        d.ellipse([px - 6, py - 6, px + 6, py + 6], fill=col + (a,))
            elif kind == "ripple":
                for i in range(2):
                    rr = 30 + ((t * 90 + i * 60) % 180)
                    a = int(170 * (1 - rr / 210))
                    if a > 0:
                        d.ellipse([CX - rr, FEET_LINE - rr * 0.32, CX + rr, FEET_LINE + rr * 0.32], outline=(200, 255, 210, a), width=3)
            elif kind == "glow":
                x, y = self.face[0], self.face[1] - 40
                for i in range(6):
                    ang = t * 2 + i * math.pi / 3
                    px = x + 150 * math.cos(ang); py = y + 90 * math.sin(ang)
                    s = 16 + 6 * math.sin(t * 5 + i)
                    d.ellipse([px - s, py - s, px + s, py + s], fill=(255, 250, 190, 90))
            elif kind in ("bubble", "heart", "star", "note", "sweat", "petal", "coin", "spark", "rain"):
                cfg = {
                    "bubble": dict(n=7, area=(W * .30, W * .70, H * .30, H * .82), size=26, color=(190, 255, 215)),
                    "heart": dict(n=5, area=(W * .34, W * .66, H * .28, H * .70), size=15, color=(255, 120, 160)),
                    "star": dict(n=7, area=(W * .28, W * .72, H * .24, H * .72), size=16, color=(255, 226, 130)),
                    "note": dict(n=5, area=(W * .34, W * .68, H * .26, H * .68), size=16, color=(150, 200, 255)),
                    "sweat": dict(n=5, area=(W * .40, W * .62, H * .22, H * .52), size=12, color=(150, 210, 255)),
                    "petal": dict(n=8, area=(W * .22, W * .78, H * .18, H * .74), size=14, color=(255, 190, 215)),
                    "coin": dict(n=6, area=(W * .36, W * .64, H * .20, H * .62), size=17, color=(255, 214, 92)),
                    "spark": dict(n=6, area=(W * .28, W * .72, H * .22, H * .70), size=15, color=(255, 245, 170)),
                    "rain": dict(n=14, area=(W * .12, W * .88, H * .06, H * .60), size=12, color=(170, 205, 255)),
                }[kind]
                cfg.update({k2: v for k2, v in o.items() if k2 in ("n", "area", "size", "color", "spread")})
                self._particles(d, t, kind, cfg["n"], cfg["area"], cfg["size"], cfg["color"], cfg.get("spread", 1.0))
        return np.asarray(img.convert("RGB")).astype(np.float32)


# ---------------------------------------------------------------- 运动程序（关键词映射）
BASE = [("breath", {"amp": 0.013, "period": 3.333}), ("sway", {"amp": 3.5, "period": 5.0, "lag": 0.6}),
        ("hair", {"amp": 6.0, "period": 4.0, "lag": 0.8, "region": "hair"})]

def _p(kind, **kw):
    """构造一个运动基元：(基元名, 参数字典)。"""
    return (kind, kw)


def _hops(*spec):
    """跳跃程序：每项 = (起跳秒, 滞空秒, 高度px)。"""
    return _p("hop", hops=list(spec))


def _eat(fx="heart"):
    """咀嚼程序：小幅点头 + 胸腔起伏。"""
    return ([_p("nod", deg=3.0, period=1.4), _p("breath", amp=0.010, period=1.4)], [fx])


def _nod(**kw):
    return _p("nod", **kw)


def _arm(side=-1, deg=14.0, period=1.0):
    return _p("arm", side=side, deg=deg, period=period)


# 动作名 → 专属运动程序（精确匹配，最高优先级）。
# 不再让冗长分镜描述里的通用词（跳/光/笑）抢占规则。
NAME_PLANS = {
    "待机呼吸休闲": ([], []),
    "原地小憩沉眠": ([_p("bob", amp=6.0, period=4.0), _p("nod", deg=3.5, period=4.0)], ["zzz"]),
    "原地漂浮踏步": ([_p("bob", amp=5.0, period=2.4), _p("leg", amp=10.0, period=1.2)], []),
    "点击回应-开心跃动": ([_hops((0.9, .50, 55), (2.1, .55, 85), (3.5, 1.4, 125), (5.7, .55, 75), (7.1, .45, 45), (8.2, .5, 60))], ["star"]),
    "点击回应-害羞惊讶": ([_p("lean", deg=-3.0, period=3.5), _p("hair", amp=5.0, period=3.5, region="hair")], ["blush"]),
    "点击回应-傲娇生气": ([_p("shake", deg=2.6, freq=7.0), _p("lean", deg=2.0, period=1.2)], ["anger"]),
    "被鼠标拖拽悬空反馈": ([_p("bob", amp=9.0, period=2.4), _p("tilt", deg=6.0, period=3.0),
                    _p("hair", amp=10.0, period=1.6, region="hair")], ["sweat"]),
    "优雅屈膝礼仪": ([_nod(deg=6.0, period=2.0), _p("bow", amp=0.06, period=4.0)], []),
    "梦幻泡泡特效": ([_p("breath", amp=0.010, period=5.0)], ["bubble"]),
    "超大伸懒腰": ([_p("stretch", amp=0.09, period=5.0), _arm(side=1, deg=20.0, period=2.5)], []),
    "小幅度原地360度旋转展示": ([_p("lean", deg=5.0, period=3.0), _p("sway", amp=7.0, period=3.0)], ["spark"]),
    "原地跳跃抓碎头顶物品": ([_hops((1.2, .55, 110), (5.4, .55, 110))], ["bang"]),
    "原地重力下蹲压缩": ([_p("crouch", amp=0.12, period=2.6)], ["bang"]),
    "原地敲击桌面互动": ([_p("bob", amp=5.0, period=0.7), _arm(side=-1, deg=16.0, period=0.7)], ["spark"]),
    "原地专心玩魔方": ([_nod(deg=4.0, period=1.6), _arm(side=-1, deg=12.0, period=1.2)], ["spark"]),
    "原地蹲下玩玩具汽车": ([_p("crouch", amp=0.09, period=6.0), _nod(deg=4.0, period=2.0)], ["spark"]),
    "玩游戏气急败坏": ([_p("shake", deg=2.6, freq=7.0), _p("lean", deg=2.0, period=1.2)], ["anger"]),
    "被吓一跳": ([_hops((2.0, .35, 60))], ["bang"]),
    "偷吃零食被抓住": ([_p("shake", deg=2.2, freq=6.0), _nod(deg=4.0, period=1.4)], ["sweat"]),
    "甩动披风下摆拍地": ([_p("sway", amp=9.0, period=1.8, region="cape"),
                    _p("hair", amp=7.0, period=1.8, region="hair")], ["ripple"]),
    "哈欠连天": ([_nod(deg=5.0, period=3.0), _p("stretch", amp=0.05, period=3.0)], ["zzz"]),
    "打瞌睡被惊醒": ([_nod(deg=5.0, period=4.0), _hops((6.0, .5, 70))], ["zzz", "bang"]),
    "螃蟹走路": ([_p("walk", amp=10.0, period=1.0), _p("shift", amp=8.0, period=2.0)], []),
    "悠闲哼歌": ([_p("bob", amp=5.0, period=1.0), _nod(deg=3.0, period=1.0)], ["note"]),
    "东张西望": ([_p("tilt", deg=8.0, period=2.4)], []),
    "原地左转奔跑": ([_p("walk", amp=12.0, period=0.55), _p("lean", deg=5.0, period=1.1)], []),
    "玩水枪": ([_arm(side=1, deg=14.0, period=0.9), _p("bob", amp=4.0, period=0.9)], ["rain"]),
    "小提琴演奏": ([_arm(side=-1, deg=18.0, period=1.1), _nod(deg=3.0, period=2.2)], ["note"]),
    "薄荷灵蝶现世": ([_p("sway", amp=7.0, period=4.0), _p("hair", amp=9.0, period=4.0, region="hair")], ["glow", "spark"]),
    "吃白饭": _eat(),
    "深度思考碎碎念": ([_p("tilt", deg=5.0, period=3.0)], ["question"]),
    "照镜子": ([_nod(deg=4.0, period=2.0), _p("lean", deg=3.0, period=2.0)], ["spark"]),
    "优雅回旋舞": ([_p("lean", deg=5.0, period=2.2), _p("sway", amp=7.0, period=2.2)], ["spark"]),
    "可爱宅舞": ([_hops((0.9, .3, 26), (2.1, .3, 26), (3.3, .3, 26), (4.5, .3, 26),
                    (5.7, .3, 26), (6.9, .3, 26), (8.1, .3, 26))], ["note"]),
    "轻快摇摆舞": ([_p("sway", amp=9.0, period=1.6)], ["note"]),
    "整体换装试色": ([_p("sway", amp=5.0, period=3.0)], ["glow"]),
    "大口吃零食": _eat(),
    "吹气球": ([_p("breath", amp=0.020, period=3.0)], ["bubble"]),
    "动物环绕": ([_hops((2.0, .35, 35), (6.0, .35, 35))], ["spark"]),
    "轻快记录": ([_arm(side=-1, deg=14.0, period=0.9), _nod(deg=3.0, period=1.8)], ["spark"]),
    "写代码": ([_arm(side=-1, deg=12.0, period=0.55), _p("bob", amp=3.0, period=0.55)], ["spark"]),
    "吃Token": _eat(fx="coin"),
    "吃早餐": _eat(), "吃午餐": _eat(), "吃晚餐": _eat(),
    "放风筝": ([_arm(side=1, deg=22.0, period=3.0), _p("bob", amp=5.0, period=3.0)], ["petal"]),
    "摇扇纳凉": ([_arm(side=1, deg=20.0, period=0.8), _p("sway", amp=4.0, period=1.6)], []),
    "吃冰淇淋融化": ([_nod(deg=3.0, period=1.4), _p("breath", amp=0.010, period=1.4)], ["sweat"]),
    "被落叶淹没": ([_p("crouch", amp=0.07, period=6.0), _p("sway", amp=5.0, period=4.0)], ["petal"]),
    "中秋赏月吃月饼": ([_nod(deg=3.0, period=1.4), _p("breath", amp=0.010, period=1.4)], ["star", "heart"]),
    "堆雪人": ([_p("crouch", amp=0.06, period=6.0), _arm(side=-1, deg=14.0, period=1.4)], ["spark"]),
    "放烟花": ([_hops((2.0, .4, 40), (6.0, .4, 40))], ["firework"]),
    "拆礼物": ([_arm(side=-1, deg=16.0, period=1.0), _p("bob", amp=5.0, period=1.0)], ["heart", "petal"]),
    "吃粽子": _eat(), "吃汤圆": _eat(), "吃饺子": _eat(), "吃糖葫芦": _eat(), "吃青团": _eat(),
    "吃腊八粥": _eat(), "吃长寿面": _eat(), "吃年糕": _eat(), "吃重阳糕": _eat(), "吃西瓜": _eat(),
    "涮火锅": ([_arm(side=-1, deg=14.0, period=1.0), _p("breath", amp=0.010, period=2.0)], ["bubble", "heart"]),
    "吃大闸蟹": ([_nod(deg=4.0, period=1.4), _p("breath", amp=0.010, period=1.4)], ["spark"]),
    "是啊，吃什么": ([_p("tilt", deg=6.0, period=2.6)], ["question"]),
    "收红包": ([_arm(side=1, deg=16.0, period=1.2)], ["coin"]),
    "舞狮头": ([_hops((1.5, .4, 60), (4.5, .4, 60), (7.5, .4, 60)), _nod(deg=5.0, period=0.8)], ["note"]),
    "写福字": ([_arm(side=-1, deg=14.0, period=1.1)], ["spark"]),
    "穿针乞巧": ([_arm(side=-1, deg=10.0, period=0.9)], ["spark"]),
    "装点圣诞树": ([_arm(side=1, deg=16.0, period=1.2), _nod(deg=3.0, period=2.0)], ["glow"]),
    "讨糖南瓜灯": ([_hops((2.0, .35, 40), (6.0, .35, 40))], ["spark"]),
    "插茱萸赏菊": ([_arm(side=1, deg=14.0, period=1.6)], ["petal"]),
    "放河灯": ([_p("crouch", amp=0.07, period=6.0)], ["ripple", "glow"]),
    "萌化小幽灵": ([_p("bob", amp=8.0, period=2.4), _p("sway", amp=5.0, period=2.4)], ["glow"]),
    "放孔明灯": ([_nod(deg=4.0, period=3.0), _p("stretch", amp=0.03, period=3.0)], ["glow", "star"]),
    "骑木马": ([_p("lean", deg=4.0, period=1.0), _p("bob", amp=7.0, period=1.0)], []),
    "变鸽子": ([_arm(side=1, deg=20.0, period=1.0)], ["spark"]),
    "凭空生花": ([_arm(side=1, deg=16.0, period=1.4)], ["petal", "glow"]),
    "扑克魔术": ([_arm(side=-1, deg=18.0, period=0.8)], ["spark"]),
    "吹笛子": ([_nod(deg=3.0, period=1.0), _arm(side=-1, deg=12.0, period=1.0)], ["note"]),
    "三球抛接": ([_p("bob", amp=6.0, period=0.6), _arm(side=1, deg=16.0, period=0.6)], ["spark"]),
    "蝴蝶蜜蜂环绕头顶开花": ([_p("sway", amp=6.0, period=3.4), _p("hair", amp=8.0, period=3.4, region="hair")], ["petal", "glow"]),
    "晨间刷牙": ([_arm(side=-1, deg=14.0, period=0.6), _nod(deg=3.0, period=1.2)], ["bubble"]),
    "撸猫": ([_arm(side=-1, deg=14.0, period=1.4)], ["heart"]),
    "踢毽子": ([_p("leg", amp=18.0, period=1.0)], ["note"]),
    "抽陀螺": ([_arm(side=-1, deg=14.0, period=0.9)], ["spark"]),
    "下五子棋": ([_arm(side=-1, deg=12.0, period=1.6), _nod(deg=4.0, period=2.4)], ["spark"]),
    "荡秋千": ([_p("lean", deg=6.0, period=2.0)], ["petal"]),
    "点击回应-挠痒咯咯笑": ([_p("shake", deg=1.8, freq=6.0), _p("bob", amp=4.0, period=0.8)], ["spark"]),
    "点击回应-元气挥手": ([_arm(side=1, deg=32.0, period=0.8), _nod(deg=4.0, period=0.8)], ["spark"]),
    "余额-钱袋满溢": ([_hops((1.5, .4, 45), (5.0, .4, 45))], ["coin", "star"]),
    "余额-金袋叮当": ([_p("bob", amp=6.0, period=1.0)], ["coin"]),
    "余额-钱袋如常": ([_nod(deg=3.0, period=2.4)], ["coin"]),
    "余额-数金皱眉": ([_p("tilt", deg=5.0, period=2.4), _arm(side=-1, deg=12.0, period=1.2)], ["coin", "question"]),
    "余额-袋空如洗": ([_nod(deg=4.0, period=3.0), _p("bob", amp=4.0, period=3.0)], ["sweat"]),
    "余额-分文不剩": ([_p("shake", deg=1.6, freq=4.0), _nod(deg=4.0, period=3.0)], ["tear"]),
    "碎碎念-擦桌碎碎念": ([_arm(side=-1, deg=16.0, period=0.9), _p("bob", amp=4.0, period=0.9)], []),
    "碎碎念-发呆碎碎念": ([_p("bob", amp=6.0, period=4.0), _nod(deg=3.5, period=4.0)], ["zzz"]),
    "碎碎念-对屏碎碎念": ([_arm(side=-1, deg=10.0, period=1.6), _nod(deg=3.0, period=1.6)], ["question"]),
    "工作状态-思考冒泡": ([_p("tilt", deg=5.0, period=3.0)], ["bubble", "question"]),
    "工作状态-忙碌点按": ([_arm(side=-1, deg=12.0, period=0.45), _p("bob", amp=3.0, period=0.45)], ["spark"]),
    "工作状态-清点归档": ([_arm(side=-1, deg=14.0, period=1.0), _nod(deg=3.0, period=2.0)], ["spark"]),
    "工作状态-原地踱步张望": ([_p("walk", amp=6.0, period=1.0), _p("tilt", deg=5.0, period=2.0)], []),
    "工作状态-雀跃庆祝": ([_hops((1.0, .5, 60), (3.2, .5, 60), (5.4, .5, 60), (7.6, .5, 60))], ["star", "note"]),
    "工作状态-垂头叹气冒汗": ([_nod(deg=6.0, period=3.0), _p("bob", amp=5.0, period=3.0)], ["sweat"]),
}

# 兜底：只在动作名没有专属映射、或名称关键词匹配不到时才用（老规则表）
DESC_RULES = [
    (r"跳|跃|蹦|欢呼|庆|胜利", [("hop", {"hops": [(0.9, .50, 55), (2.1, .55, 85), (3.5, 1.4, 125), (5.7, .55, 75), (7.1, .45, 45), (8.2, .5, 60)]})], ["star"]),
    (r"挥手|招手|打招呼|问好", [("arm", {"side": 1, "deg": 30, "period": 1.0}), ("nod", {"deg": 4, "period": 1.0})], ["spark"]),
    (r"点头|颔首|鞠躬|行礼|屈膝|礼仪", [("nod", {"deg": 5.5, "period": 1.6})], []),
    (r"摇头|晃头|东张西望|张望|环顾", [("tilt", {"deg": 7.0, "period": 2.2})], []),
    (r"转|回旋|旋转|转身", [("lean", {"deg": 4.0, "period": 2.0}), ("sway", {"amp": 6.0, "period": 2.0})], ["spark"]),
    (r"颤|抖|发冷|害怕|紧张|生气|怒|顿足|跺脚", [("shake", {"deg": 2.6, "freq": 7.0})], []),
    (r"伸懒腰|伸展|放松|舒展", [("stretch", {"amp": 0.07, "period": 6.0})], []),
    (r"走|踏步|踱步|跑|奔", [("walk", {"amp": 9.0, "period": 0.9}), ("lean", {"deg": 2.0, "period": 1.8})], []),
    (r"睡|困|打盹|眯|休息|做梦", [("bob", {"amp": 6.0, "period": 4.0}), ("nod", {"deg": 3.5, "period": 4.0})], ["zzz"]),
    (r"害羞|脸红|不好意思|捂脸", [("lean", {"deg": -3.0, "period": 3.5}), ("hair", {"amp": 4.0, "period": 3.5, "region": "hair"})], ["blush"]),
    (r"惊讶|吃惊|震惊|意外", [("stretch", {"amp": 0.05, "period": 4.0})], ["bang"]),
    (r"疑惑|思考|想|沉思|琢磨|研究", [("tilt", {"deg": 5.0, "period": 3.0})], ["question"]),
    (r"哭|泪|委屈|伤心|难过", [("shake", {"deg": 1.4, "freq": 5.0}), ("nod", {"deg": 3.0, "period": 2.5})], ["tear"]),
    (r"汗|累|疲惫|叹气|垂头", [("nod", {"deg": 4.0, "period": 3.0}), ("bob", {"amp": 5.0, "period": 3.0})], ["sweat"]),
    (r"泡|气泡|吐泡", [("breath", {"amp": 0.010, "period": 5.0})], ["bubble"]),
    (r"烟花|礼花|爆炸|绽放", [("hop", {"hops": [(2.0, .4, 40), (6.0, .4, 40)]})], ["firework"]),
    (r"星|闪|发光|亮|光|萤", [("breath", {"amp": 0.010, "period": 2.5})], ["star", "spark"]),
    (r"心|爱|喜欢|恋|亲", [("breath", {"amp": 0.014, "period": 2.5})], ["heart"]),
    (r"音符|唱|哼|音乐|歌", [("nod", {"deg": 3.0, "period": 1.0}), ("bob", {"amp": 5.0, "period": 1.0})], ["note"]),
    (r"花|花瓣|春|樱|礼物|拆", [("sway", {"amp": 5.0, "period": 3.0})], ["petal"]),
    (r"钱|金|余额|币|财|赚|元宝", [("bob", {"amp": 5.0, "period": 2.0})], ["coin"]),
    (r"雨|伞|阴天|水", [("lean", {"deg": 2.5, "period": 3.0})], ["rain"]),
    (r"球|玩|游戏|挠|戳|拍", [("bob", {"amp": 7.0, "period": 1.2}), ("arm", {"side": -1, "deg": 14, "period": 1.2})], ["spark"]),
    (r"吃|喝|蛋糕|食|饭|茶|咖啡|点心", [("nod", {"deg": 3.0, "period": 1.4}), ("breath", {"amp": 0.010, "period": 1.4})], ["heart"]),
    (r"水|涟漪|湖|海|漂浮|浮", [("bob", {"amp": 7.0, "period": 3.0}), ("sway", {"amp": 6.0, "period": 3.0})], ["ripple"]),
    (r"魔法|灵|仙|飘|飞舞|蝶", [("sway", {"amp": 7.0, "period": 4.0}), ("hair", {"amp": 9.0, "period": 4.0, "region": "hair"})], ["glow", "spark"]),
    (r"秋千|荡|摇椅|秋", [("lean", {"deg": 5.0, "period": 2.2})], ["petal"]),
    (r"炮|炸|冲|击|打|拳|锤", [("shake", {"deg": 3.0, "freq": 4.0}), ("stretch", {"amp": 0.04, "period": 1.5})], ["bang"]),
]

# 精确动作名表（已手工编排的动作）优先于关键词兜底表
RULES = [(re.escape(k), list(ps), list(fs)) for k, (ps, fs) in NAME_PLANS.items()] + DESC_RULES

def plan_for(name: str, desc: str = ""):
    """按动作名（必要时结合分镜文本）挑运动程序。"""
    hit = NAME_PLANS.get(name)
    if hit:
        return {"prims": list(BASE) + list(hit[0]), "effects": [(f, {}) for f in hit[1]]}
    txt = name + " " + desc
    prims, fx = [], []
    for rx, ps, fs in RULES:
        if re.search(rx, txt):
            for p in ps:
                if p[0] == "hop" and any(q[0] == "hop" for q in prims):
                    continue
                prims.append(p)
            for f in fs:
                if f not in fx:
                    fx.append(f)
            break
    if not prims:
        prims = list(BASE)
    else:
        prims = list(BASE) + prims
    return {"prims": prims, "effects": [(f, {}) for f in fx]}


# ---------------------------------------------------------------- 动作清单
def action_list():
    names = []
    for p in sorted(PROMPT_DIR.glob("*.txt")):
        m = re.match(r"(\d+)-(.+)\.txt$", p.name)
        if m:
            names.append(m.group(2))
    return names

def action_desc(name: str) -> str:
    """从改写后的完整提示词里取该动作的「动作概述 + 按秒分割画面」文本（给关键词匹配用）。"""
    f = PROMPT_DIR / next((p.name for p in PROMPT_DIR.glob("*-" + name + ".txt")), "")
    if not f.exists():
        return ""
    t = f.read_text(encoding="utf-8")
    i = t.rfind("\n## ")
    return t[i:] if i > 0 else t[-1500:]


# ---------------------------------------------------------------- 渲染
def render_one(name: str, fig_path=FIG_PATH, out_dir=OUT_DIR, quiet=False):
    fig = Figure(fig_path)
    prog = plan_for(name, action_desc(name))
    eff = Effects(fig)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{name}.mp4"
    cmd = [str(FFMPEG), "-y", "-loglevel", "error", "-nostats",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", str(out)]
    # 逐帧流式喂给 ffmpeg（不要把 240 帧堆在内存里），stderr 必须持续排空否则管道死锁
    err = []
    with open(os.devnull, "wb") as devnull:
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=devnull, stderr=subprocess.PIPE)
        for i in range(N_FRAMES):
            t = 0.0 if i == N_FRAMES - 1 else i / FPS     # 末帧 = 首帧
            dy, dx = fields(t, prog, fig)
            warped = fig.sample(dy, dx)
            frame = fig.to_canvas(warped)
            frame = eff.draw(frame, t, prog["effects"])
            p.stdin.write(np.clip(frame, 0, 255).astype(np.uint8).tobytes())
        p.stdin.close()
        for line in p.stderr:
            err.append(line)
        rc = p.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg failed for {name}: {b''.join(err).decode('utf-8', 'ignore')[:400]}")
    if not quiet:
        print(f"  [{name}] {out.name} {out.stat().st_size/1024:.0f} KB  fx={[f[0] for f in prog['effects']]}")
    return str(out)


def _worker(args):
    name, = args
    try:
        return name, True, render_one(name, quiet=True)
    except Exception as e:      # noqa: BLE001
        return name, False, str(e)[:200]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--only", nargs="*", default=[])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--report", default="")
    args = ap.parse_args()

    names = action_list()
    if args.report:
        lines = ["# 动作 → 运动程序映射表", "", f"共 {len(names)} 个动作。运动基元 = 呼吸/摇摆/点头/挥手/跳跃/走路/颤抖/伸展/鞠躬…；特效 = 气泡/星星/爱心/汗滴/音符/烟花/硬币/花瓣/雨/Zzz 等。", "",
                 "| 序号 | 动作名 | 运动基元 | 特效 |", "|---|---|---|---|"]
        for i, n in enumerate(names, 1):
            pr = plan_for(n, action_desc(n))
            pstr = "、".join(p[0] for p in pr["prims"] if p[0] not in ("breath", "sway", "hair"))
            fstr = "、".join(f[0] for f in pr["effects"]) or "—"
            lines.append(f"| {i:03d} | {n} | {pstr or '基础待机'} | {fstr} |")
        p = ROOT / args.report
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(lines), encoding="utf-8")
        print(f"报告已写：{p}")
        return
    if args.list:
        for i, n in enumerate(names, 1):
            pr = plan_for(n, action_desc(n))
            print(f"{i:03d} {n}  ←  " + "、".join(p[0] for p in pr["prims"]) + "  fx=" + ",".join(f[0] for f in pr["effects"]))
        return

    todo = args.only or (names[:args.limit] if args.limit else names if args.all else [])
    if not todo:
        ap.error("请给 --only/--all/--list/--report")
    print(f"渲染 {len(todo)} 个动作 → {OUT_DIR}（jobs={args.jobs}）")
    import time
    t0 = time.time()
    if args.jobs > 1:
        with ProcessPoolExecutor(max_workers=args.jobs) as ex:
            futs = [ex.submit(_worker, (n,)) for n in todo]
            for k, fut in enumerate(as_completed(futs), 1):
                n, ok, info = fut.result()
                print(f"[{k}/{len(todo)}] {'OK ' if ok else 'FAIL'} {n} {'' if ok else info}")
    else:
        for k, n in enumerate(todo, 1):
            render_one(n)
            print(f"[{k}/{len(todo)}] done")
    print(f"用时 {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
