# -*- coding: utf-8 -*-
"""
生成「端到端验证」用的合成素材（不需要任何 AI 工具）：

  1) video/test-stand.mp4      1280x720 / 24fps / 10s，纯 #00FF00 绿幕 + 会呼吸起伏的 Q 版小人，
                               右下角带一个「模拟 AI 工具水印」（灰色圆角块 + 三条杠）。
  2) work/black_10s.mp4        同尺寸同帧率的纯黑视频 + 同一个水印，用来生成去水印 mask。

用它可以完整跑通：make_mask_black → watermark_step01 → chroma_step02 → normalize_step03 → encode_thumbs。

用法: python make_test_videos.py
"""
from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
FFMPEG = str(ROOT / ".tools" / "ffmpeg-9.0.1-essentials_build" / "bin" / "ffmpeg.exe")
VIDEO_DIR = ROOT / "video"
WORK_DIR = ROOT / "work"

W, H, FPS, SECONDS = 1280, 720, 24, 10
N = FPS * SECONDS
SS = 2  # 超采样倍数（抗锯齿，用来考验抠像的边缘羽化）

GREEN = (0, 255, 0)
# 角色配色（取自设定卡）
HAIR = (235, 236, 234)
HAIR_SH = (209, 207, 207)
MINT = (167, 222, 207)
PALE = (207, 232, 200)
DARK = (37, 30, 36)
NAVY = (37, 43, 87)
GOLD = (216, 177, 111)
ORANGE = (240, 153, 51)
SKIN = (252, 232, 225)
WM = (200, 200, 200)  # 模拟水印颜色


def draw_watermark(d: ImageDraw.ImageDraw, ss: int, alpha: float = 0.92) -> None:
    """右下角模拟水印：圆角块 + 三条杠。位置与透明度恒定（对应真实工具的单帧水印）。
    刻意放在角色包围盒之外（角色 x 490~790 / y 155~610），便于肉眼验证「去水印是否干净」。"""
    def S(v):
        return v * ss
    x0, y0, x1, y1 = S(980), S(630), S(1250), S(690)
    d.rounded_rectangle([x0, y0, x1, y1], radius=S(12), fill=WM + (int(255 * alpha),))
    for i in range(3):
        bx = S(1000 + i * 62)
        d.rounded_rectangle([bx, S(650), bx + S(48), S(670)], radius=S(6),
                            fill=(235, 235, 235, int(255 * alpha)))


def draw_character(d: ImageDraw.ImageDraw, dy: float, bubble_x: float, ss: int) -> None:
    """Q 版小人替身：银白头发 + 深蓝披风 + 薄荷下摆 + 长筒袜短靴，按 dy 做呼吸起伏。"""
    cx = 640 * ss
    def S(v):  # 坐标缩放
        return v * ss

    head_cy = S(275) + dy * ss
    head_r = S(72) + 0
    # —— 披风（薄荷内衬，画在身后）——
    d.polygon([(cx - S(150), S(300) + dy * ss), (cx + S(150), S(300) + dy * ss),
               (cx + S(175), S(540) + dy * ss), (cx + S(90), S(505) + dy * ss),
               (cx, S(560) + dy * ss), (cx - S(90), S(505) + dy * ss),
               (cx - S(175), S(540) + dy * ss)], fill=MINT + (255,))
    d.polygon([(cx - S(120), S(300) + dy * ss), (cx + S(120), S(300) + dy * ss),
               (cx + S(140), S(500) + dy * ss), (cx, S(545) + dy * ss),
               (cx - S(140), S(500) + dy * ss)], fill=PALE + (255,))
    # —— 腿 + 靴 ——
    for sx in (-1, 1):
        lx = cx + sx * S(42)
        d.rounded_rectangle([lx - S(26), S(470) + dy * ss, lx + S(26), S(575) + dy * ss],
                            radius=S(20), fill=DARK + (255,))
        d.rounded_rectangle([lx - S(30), S(555) + dy * ss, lx + S(30), S(600) + dy * ss],
                            radius=S(14), fill=NAVY + (255,))
        d.rounded_rectangle([lx - S(30), S(590) + dy * ss, lx + S(30), S(602) + dy * ss],
                            radius=S(6), fill=(250, 250, 250, 255))
        d.ellipse([lx - S(26), S(540) + dy * ss, lx + S(26), S(566) + dy * ss],
                  fill=ORANGE + (255,))
    # —— 躯干：深蓝黑披风外套 ——
    d.polygon([(cx - S(96), S(300) + dy * ss), (cx + S(96), S(300) + dy * ss),
               (cx + S(112), S(470) + dy * ss), (cx - S(112), S(470) + dy * ss)],
              fill=DARK + (255,))
    # 金色菱形扣 + 橙色蝶翼胸针
    d.polygon([(cx, S(318) + dy * ss), (cx + S(22), S(348) + dy * ss),
               (cx, S(378) + dy * ss), (cx - S(22), S(348) + dy * ss)], fill=GOLD + (255,))
    d.polygon([(cx - S(46), S(370) + dy * ss), (cx - S(8), S(392) + dy * ss),
               (cx - S(46), S(414) + dy * ss), (cx - S(70), S(392) + dy * ss)],
              fill=ORANGE + (255,))
    d.polygon([(cx + S(46), S(370) + dy * ss), (cx + S(8), S(392) + dy * ss),
               (cx + S(46), S(414) + dy * ss), (cx + S(70), S(392) + dy * ss)],
              fill=ORANGE + (255,))
    # —— 长发（银白，垂到腰下）——
    d.ellipse([cx - S(114), head_cy - S(120), cx + S(114), head_cy + S(44)],
              fill=HAIR + (255,))
    for sx in (-1, 1):
        lx = cx + sx * S(96)
        d.ellipse([lx - S(44), head_cy - S(24), lx + S(44), S(468) + dy * ss],
                  fill=HAIR_SH + (255,))
    # —— 脸 ——
    d.ellipse([cx - head_r, head_cy - head_r, cx + head_r, head_cy + head_r],
              fill=SKIN + (255,))
    # 眼睛（紫粉上 / 浅蓝下）
    for sx in (-1, 1):
        ex = cx + sx * S(30)
        d.ellipse([ex - S(17), head_cy - S(6), ex + S(17), head_cy + S(30)],
                  fill=(115, 191, 247, 255))
        d.ellipse([ex - S(17), head_cy - S(6), ex + S(17), head_cy + S(12)],
                  fill=(212, 135, 183, 255))
        d.ellipse([ex - S(6), head_cy + S(2), ex + S(2), head_cy + S(11)],
                  fill=(255, 255, 255, 255))
    d.arc([cx - S(22), head_cy + S(36), cx + S(22), head_cy + S(62)],
          start=15, end=165, fill=(150, 90, 90, 255), width=S(3))
    # —— 发箍 + 叶片发饰 ——
    d.rounded_rectangle([cx - S(74), head_cy - S(84), cx + S(74), head_cy - S(56)],
                        radius=S(12), fill=(26, 26, 26, 255))
    d.polygon([(cx - S(20), head_cy - S(76)), (cx + S(6), head_cy - S(70)),
               (cx - S(20), head_cy - S(64))], fill=(100, 174, 174, 255))
    d.ellipse([cx + S(86), head_cy - S(96), cx + S(126), head_cy - S(46)],
              fill=MINT + (255,))
    # —— 半透明漂浮泡泡（考验 alpha 通道保真）——
    d.ellipse([bubble_x - S(46), S(360) - S(46), bubble_x + S(46), S(360) + S(46)],
              fill=(167, 222, 207, 110))
    d.ellipse([bubble_x - S(30), S(346) - S(30), bubble_x + S(30), S(346) + S(30)],
              fill=(255, 255, 255, 90))


def render_frame(i: int, with_watermark: bool, black_bg: bool) -> Image.Image:
    canvas = Image.new("RGB", (W * SS, H * SS), (0, 0, 0) if black_bg else GREEN)
    d = ImageDraw.Draw(canvas, "RGBA")
    if black_bg:
        d.rectangle([0, 0, W * SS, H * SS], fill=(0, 0, 0, 255))
    else:
        t = i / FPS
        dy = 10.0 * math.sin(2 * math.pi * t / 2.5)          # 呼吸起伏 ±10px
        bubble_x = 640 + 190 * math.sin(2 * math.pi * t / 4.0)
        draw_character(d, dy, bubble_x, SS)
    if with_watermark:
        draw_watermark(d, SS)
    return canvas.resize((W, H), Image.LANCZOS)


def encode(frames, dst: Path, label: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    p = subprocess.Popen(
        [FFMPEG, "-y", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "fast", str(dst)],
        stdin=subprocess.PIPE)
    for f in frames:
        p.stdin.write(np.asarray(f, dtype=np.uint8).tobytes())
    p.stdin.close()
    rc = p.wait()
    size = dst.stat().st_size / 1024 if dst.exists() else 0
    print(f"{label}: {dst}  ({size:.0f} KB, rc={rc})")


def main() -> int:
    print(f"生成 {N} 帧 @ {W}x{H} {FPS}fps ...")
    encode((render_frame(i, True, False) for i in range(N)),
           VIDEO_DIR / "test-stand.mp4", "绿幕测试视频(带水印)")
    encode((render_frame(i, True, True) for i in range(N)),
           WORK_DIR / "black_10s.mp4", "纯黑参考视频(带同一水印)")
    print("\n下一步：")
    print(f"  python scripts/make_mask_black.py       # 由 work/black_10s.mp4 生成 video/watermark_mask_v5.mkv")
    print(f"  powershell -File run_pipeline.ps1       # 一键跑完整条素材链")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
