# -*- coding: utf-8 -*-
"""make_first_frame.py —— 生成即梦「图生视频 / 首尾帧」用的首帧图：
把抠好的正面立绘按提示词强制构图（头顶 20% / 脚底 85% / 水平居中）合成到
1280x720 纯绿 #00FF00 画布上。输出：
  character/first_frame_green.png        首帧（也是尾帧，用于首尾帧模式保证首尾一致）
  character/first_frame_green_small.png  720x405 预览用缩略
"""
import sys
import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")

ROOT = r"D:\wd\deepseek-harness\default-workspace\dsh-pet-custom"
W, H = 1280, 720
GREEN = (0, 255, 0)
HEAD_LINE = int(H * 0.20)   # 144
FEET_LINE = int(H * 0.85)   # 612
CX = W // 2

fig = np.asarray(Image.open(ROOT + r"\character\front_stand.png").convert("RGBA")).astype(np.float32)
frgb, fa = fig[:, :, :3], np.clip(fig[:, :, 3], 0, 255)
fa[fa >= 200] = 255.0
fig_h, fig_w = fa.shape
S0 = (FEET_LINE - HEAD_LINE) / fig_h

w = max(1, int(round(fig_w * S0)))
h = max(1, int(round(fig_h * S0)))
r = np.asarray(Image.fromarray(np.dstack([frgb, fa]).astype(np.uint8), "RGBA").resize((w, h), Image.LANCZOS)).astype(np.float32)
rf, ra = r[:, :, :3], r[:, :, 3] / 255.0
ra3 = ra[:, :, None]
canvas = np.zeros((H, W, 3), np.float32)
canvas[:] = GREEN
x0 = CX - w // 2
y0 = FEET_LINE - h
canvas[y0:y0 + h, x0:x0 + w] = rf * ra3 + GREEN * (1 - ra3)
out = canvas.astype(np.uint8)

# 校验：绿幕纯度 + 角色包围盒
g = (out[:, :, 0] == 0) & (out[:, :, 1] == 255) & (out[:, :, 2] == 0)
non = ~g
ys, xs = np.where(non)
print(f"figure {fig_w}x{fig_h} -> scale {S0:.4f} -> {w}x{h} at x{x0} y{y0}")
print(f"green pixels {g.mean()*100:.2f}%  bbox x{xs.min()}..{xs.max()} y{ys.min()}..{ys.max()}")
print(f"head_line {HEAD_LINE} feet_line {FEET_LINE} -> top {ys.min()} bottom {ys.max()} center_x {(xs.min()+xs.max())//2}")

im = Image.fromarray(out, "RGB")
im.save(ROOT + r"\character\first_frame_green.png")
im.resize((720, 405), Image.LANCZOS).save(ROOT + r"\character\first_frame_green_small.png")
print("written first_frame_green.png / first_frame_green_small.png")
