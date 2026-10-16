# -*- coding: utf-8 -*-
"""probe_feet.py —— 确认三立绘的真实底边（y 400 以下是否还有脚/地面），并定位正面立绘的精确 bbox。"""
import sys
import numpy as np
from PIL import Image
from scipy.ndimage import label

sys.stdout.reconfigure(encoding="utf-8")

SRC = r"D:\wd\deepseek-harness\default-workspace\dsh-pet-custom\character\reference.png"
a = np.asarray(Image.open(SRC).convert("RGBA")).astype(int)
rgb = a[:, :, :3]
alpha = a[:, :, 3]

band = alpha[0:560, :] > 16
lab, n = label(band)
for l in range(1, n + 1):
    ys, xs = np.where(lab == l)
    if len(ys) < 800:
        continue
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    print(f"块{l}: bbox x{x0}..{x1} y{y0}..{y1} ({x1-x0}x{y1-y0}px) 面积{len(ys)}")

# 底部区域逐行看正面立绘（x38..388）的 alpha 分布
print("\n正面立绘列带 (x38..388) 底部逐行不透明px 与 x 范围:")
for y in range(440, 561, 8):
    row = alpha[y, 38:388] > 16
    if row.any():
        xs = np.where(row)[0]
        print(f"  y{y:3}: {int(row.sum()):4d}px  x范围 {38+xs.min()}..{38+xs.max()}")
    else:
        print(f"  y{y:3}: 0px")
