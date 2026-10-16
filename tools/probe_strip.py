# -*- coding: utf-8 -*-
"""probe_strip.py —— 重新自底向上盘点参考图底部条带（y 400..874）的所有内容块。
输出每块：bbox、尺寸、不透明占比、均值 RGB、近白占比、近薄荷占比 + 粗 ASCII 形状。
"""
import sys
import numpy as np
from PIL import Image
from scipy.ndimage import label

sys.stdout.reconfigure(encoding="utf-8")

SRC = r"D:\wd\deepseek-harness\default-workspace\dsh-pet-custom\character\reference.png"
STRIP_Y0 = 400

a = np.asarray(Image.open(SRC).convert("RGBA")).astype(int)
rgb = a[:, :, :3]
alpha = a[:, :, 3]
H, W = alpha.shape
print(f"image {W}x{H}")

# 1) 全图逐行不透明像素统计，找内容带
rowsum = (alpha > 16).sum(axis=1)
bands = []
inb = False
for y in range(H):
    if rowsum[y] > 0 and not inb:
        y0 = y
        inb = True
    elif rowsum[y] == 0 and inb:
        bands.append((y0, y))
        inb = False
if inb:
    bands.append((y0, H))
print("全图内容带:", bands)

# 2) 条带连通域分析
strip = alpha[STRIP_Y0:, :] > 16
lab, n = label(strip)
print(f"条带 (y{STRIP_Y0}..{H}) 连通域 {n} 个")
rows = []


def ascii_block(blk_alpha, blk_rgb, cols=44, rows=18):
    y0, y1, x0, x1 = blk_alpha
    sub = alpha[y0:y1, x0:x1]
    subr = rgb[y0:y1, x0:x1]
    h, w = sub.shape
    lines = []
    for r in range(rows):
        line = ""
        for c in range(cols):
            m = sub[r * h // rows:(r + 1) * h // rows, c * w // cols:(c + 1) * w // cols]
            vis = m > 16
            if not vis.any():
                line += " "
            else:
                lv = (0.299 * subr[r * h // rows:(r + 1) * h // rows, c * w // cols:(c + 1) * w // cols, 0]
                      + 0.587 * subr[r * h // rows:(r + 1) * h // rows, c * w // cols:(c + 1) * w // cols, 1]
                      + 0.114 * subr[r * h // rows:(r + 1) * h // rows, c * w // cols:(c + 1) * w // cols, 2])[vis].mean()
                line += " .:-=+*#%@"[min(9, int(lv // 26))]
        lines.append(line)
    return "\n".join(lines)


comps = []
for l in range(1, n + 1):
    ys, xs = np.where(lab == l)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    comps.append((l, y0, y1, x0, x1, len(ys)))

for l, y0, y1, x0, x1, area in comps:
    blk_a = alpha[STRIP_Y0 + y0:STRIP_Y0 + y1, x0:x1]
    blk_r = rgb[STRIP_Y0 + y0:STRIP_Y0 + y1, x0:x1]
    vis = blk_a > 128
    mr = blk_r[:, :, 0][vis].mean().round(0)
    mg = blk_r[:, :, 1][vis].mean().round(0)
    mb = blk_r[:, :, 2][vis].mean().round(0)
    nw = ((blk_r[:, :, 0] > 240) & (blk_r[:, :, 1] > 240) & (blk_r[:, :, 2] > 240) & vis).mean() * 100
    nm = ((abs(blk_r[:, :, 0] - 120) < 60) & (blk_r[:, :, 1] > 140) & (blk_r[:, :, 2] > 130) & (blk_r[:, :, 1] < 230) & vis).mean() * 100
    print(f"\n=== 块{l} 条带bbox x{x0}..{x1} y{y0}..{y1}  (原图 x{x0}..{x1} y{STRIP_Y0+y0}..{STRIP_Y0+y1}) "
          f"{x1-x0}x{y1-y0}px 不透明占比{vis.mean()*100:.0f}% 均值RGB({mr:.0f},{mg:.0f},{mb:.0f}) 近白{nw:.0f}% 近薄荷{nm:.0f}%")
    print(ascii_block((STRIP_Y0 + y0, STRIP_Y0 + y1, x0, x1), rgb, 44, 12))
