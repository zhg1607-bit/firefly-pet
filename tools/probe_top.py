# -*- coding: utf-8 -*-
"""probe_top.py —— 盘点参考图顶部三视图区域（y 0..400）的内容块 + 眼睛色定位正面视图。"""
import sys
import numpy as np
from PIL import Image
from scipy.ndimage import label

sys.stdout.reconfigure(encoding="utf-8")

SRC = r"D:\wd\deepseek-harness\default-workspace\dsh-pet-custom\character\reference.png"
a = np.asarray(Image.open(SRC).convert("RGBA")).astype(int)
rgb = a[:, :, :3]
alpha = a[:, :, 3]
H, W = alpha.shape

band = alpha[:400, :] > 16
lab, n = label(band)
print(f"顶部带 (y0..400) 连通域 {n} 个（面积>=800 才列）")
for l in range(1, n + 1):
    ys, xs = np.where(lab == l)
    if len(ys) < 800:
        continue
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    blk_r = rgb[y0:y1, x0:x1]
    blk_a = alpha[y0:y1, x0:x1] > 128
    # 眼睛色：紫粉 D487B7 / 蓝 73BFF7
    eyemask = (((abs(blk_r[:, :, 0] - 212) < 45) & (abs(blk_r[:, :, 1] - 135) < 45) & (abs(blk_r[:, :, 2] - 183) < 45))
               | ((abs(blk_r[:, :, 0] - 115) < 45) & (abs(blk_r[:, :, 1] - 191) < 45) & (abs(blk_r[:, :, 2] - 247) < 45))) & blk_a
    eyecnt = eyemask.sum()
    # 皮肤色 FCE8E1 / 发色 EBECEA
    skincnt = ((abs(blk_r[:, :, 0] - 252) < 20) & (abs(blk_r[:, :, 1] - 232) < 20) & (abs(blk_r[:, :, 2] - 225) < 20) & blk_a).sum()
    haircnt = ((abs(blk_r[:, :, 0] - 235) < 20) & (abs(blk_r[:, :, 1] - 236) < 20) & (abs(blk_r[:, :, 2] - 234) < 20) & blk_a).sum()
    # 黑色（深蓝黑服饰 #251E24/#252B57）
    darkcnt = ((blk_r[:, :, 0] < 70) & (blk_r[:, :, 1] < 70) & (blk_a)).sum()
    print(f"块{l}: bbox x{x0}..{x1} y{y0}..{y1} ({x1-x0}x{y1-y0}px) 不透明{blk_a.mean()*100:.0f}% "
          f"眼睛色px={int(eyecnt)} 皮肤px={int(skincnt)} 发色px={int(haircnt)} 深色服饰px={int(darkcnt)}")
