# -*- coding: utf-8 -*-
"""extract_front.py —— 从 reference.png 里把「正面立绘」按连通域干净抠出（带 alpha），
并切出头部（供通知图标用）。不依赖任何颜色抠除：参考图本身就是 RGBA 透明背景。"""
import sys
import numpy as np
from PIL import Image, ImageFilter
from scipy.ndimage import label, binary_dilation

sys.stdout.reconfigure(encoding="utf-8")

ROOT = r"D:\wd\deepseek-harness\default-workspace\dsh-pet-custom"
SRC = ROOT + r"\character\reference.png"

a = np.asarray(Image.open(SRC).convert("RGBA")).astype(np.int32)
rgb = a[:, :, :3]
alpha = a[:, :, 3]

# 正面立绘 = 顶部连通域 块5（x38..388, y19..511），直接取该块的 mask 做裁剪
lab, n = label(alpha > 16)
mask = lab == 5
ys, xs = np.where(mask)
y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
print(f"正面立绘 bbox: x{x0}..{x1} y{y0}..{y1} = {x1-x0}x{y1-y0}")

# 外扩 3px 并轻微膨胀，保住抗锯齿边缘
m = 3
y0, y1, x0, x1 = max(0, y0 - m), y1 + m, max(0, x0 - m), x1 + m
sub_mask = binary_dilation(mask[y0:y1, x0:x1], iterations=2)
sub_rgb = rgb[y0:y1, x0:x1]
sub_a = alpha[y0:y1, x0:x1]

# 用膨胀后的 mask 兜底：mask 内保留原 alpha，mask 外透明
final_a = np.where(sub_mask, np.maximum(sub_a, 1), 0).astype(np.uint8)
fig = np.dstack([sub_rgb.astype(np.uint8), final_a])

im = Image.fromarray(fig, "RGBA")
im.save(ROOT + r"\character\front_stand.png")
h, w = final_a.shape
op = (final_a > 16).mean()
print(f"front_stand.png: {w}x{h}, 不透明占比 {op:.1%}, alpha min/max = {final_a.min()}/{final_a.max()}")

# ---- 先检查内部 alpha 是否 255（若有半透明内部，扣像会透绿，需归一化）----
interior = final_a > 200
vals, counts = np.unique(final_a[interior], return_counts=True)
print("\n内部(alpha>200) alpha 分布:")
for v, c in zip(vals, counts):
    print(f"  {v}: {c} ({c/counts.sum():.1%})")

# ---- 找头部下边界：逐行皮肤色像素 ----
skin = (rgb[:, :, 0] >= 240) & (rgb[:, :, 0] <= 255) & (rgb[:, :, 1] >= 210) & (rgb[:, :, 1] <= 240) \
     & (rgb[:, :, 2] >= 185) & (rgb[:, :, 2] <= 225) & (alpha > 128)
rowskin = skin[y0:y1, :].sum(axis=1)
print("\n正面立绘逐行皮肤色像素（每 5 行）:")
for i in range(0, h, 5):
    s = int(rowskin[i:i+5].sum())
    if s:
        print(f"  y{y0+i}: {s}")

# 头部底边 = 脸部皮肤带（y~216..246 峰值）结束 + 下巴/颈 22px
head_bottom = (246 - y0) + 22
print(f"头部底边: y{y0 + head_bottom}")

head_crop = fig[:head_bottom, :, :]
# 头部内容框裁边
hmask = head_crop[:, :, 3] > 16
hys, hxs = np.where(hmask)
hy0, hy1, hx0, hx1 = hys.min(), hys.max() + 1, hxs.min(), hxs.max() + 1
head = head_crop[hy0:hy1, hx0:hx1, :]
Image.fromarray(head, "RGBA").save(ROOT + r"\character\head.png")
print(f"head.png: {head.shape[1]}x{head.shape[0]}")
