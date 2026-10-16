# -*- coding: utf-8 -*-
"""probe_faces.py —— 在参考图下半部分定位「表情参考」4 个头像的真实位置。
判据：皮肤像素多 + 眼睛色像素多（紫粉/蓝）+ 近正方 bbox。"""
import sys
import numpy as np
from PIL import Image
from scipy.ndimage import label

sys.stdout.reconfigure(encoding="utf-8")

REF = r"D:\wd\deepseek-harness\default-workspace\dsh-pet-custom\character\reference.png"
a = np.asarray(Image.open(REF).convert("RGBA")).astype(np.int32)
rgb, alpha = a[:, :, :3], a[:, :, 3]
H, W = alpha.shape
print(f"reference {W}x{H}")

R, G, B = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
skin = (R >= 240) & (R <= 255) & (G >= 205) & (G <= 240) & (B >= 180) & (B <= 228)
eye = (((np.abs(R - 212) < 60) & (np.abs(G - 135) < 70) & (np.abs(B - 183) < 60)) |
       ((np.abs(R - 115) < 70) & (np.abs(G - 191) < 65) & (np.abs(B - 247) < 50)))

lab, n = label(alpha > 16)
print(f"连通域 {n} 个，列出 y0>380 且面积>500 的块：")
rows = []
for l in range(1, n + 1):
    ys, xs = np.where(lab == l)
    if len(ys) < 500:
        continue
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    if y0 < 380:
        continue
    m = lab == l
    sk, ey = int((m & skin).sum()), int((m & eye).sum())
    mean = rgb[m].mean(axis=0).astype(int).tolist()
    rows.append((y0, x0, x1, y1, len(ys), sk, ey, mean, y1 - y0, x1 - x0))
rows.sort()
for y0, x0, x1, y1, area, sk, ey, mean, hh, ww in rows:
    print(f"  x{x0:4}..{x1:4} y{y0:4}..{y1:4} ({ww:3}x{hh:3}) 面积{area:6} 皮肤{sk:6} 眼{ey:5} 均值{mean}")
