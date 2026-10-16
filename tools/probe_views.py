# -*- coding: utf-8 -*-
"""probe_views.py —— ASCII 渲染三个立绘块，识别正面/侧面/背面。"""
import sys
import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")

SRC = r"D:\wd\deepseek-harness\default-workspace\dsh-pet-custom\character\reference.png"
a = np.asarray(Image.open(SRC).convert("RGBA")).astype(int)
rgb = a[:, :, :3]
alpha = a[:, :, 3]

luma = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
CHARS = " .:-=+*#%@"


def render(x0, x1, y0, y1, cols=44, rows=34, title=""):
    print(f"=== {title} x{x0}..{x1} y{y0}..{y1} ===")
    for r in range(rows):
        line = ""
        for c in range(cols):
            m = alpha[y0 + r * (y1 - y0) // rows:y0 + (r + 1) * (y1 - y0) // rows,
                      x0 + c * (x1 - x0) // cols:x0 + (c + 1) * (x1 - x0) // cols] > 16
            if not m.any():
                line += " "
            else:
                lv = luma[y0 + r * (y1 - y0) // rows:y0 + (r + 1) * (y1 - y0) // rows,
                          x0 + c * (x1 - x0) // cols:x0 + (c + 1) * (x1 - x0) // cols][m].mean()
                line += CHARS[min(9, int(lv // 26))]
        print(line)


render(38, 388, 19, 400, 44, 30, "左块(疑似正面)")
render(474, 807, 19, 400, 44, 30, "中块(疑似侧面)")
render(818, 1158, 21, 400, 44, 30, "右块(疑似背面)")
render(1170, 1296, 17, 400, 24, 30, "最右窄块")

# 立绘底部是否被 y=400 截断
rowsum = (alpha > 16).sum(axis=1)
print("\ny 行不透明px（380..560）:")
for y in range(380, 560, 10):
    print(f"  y{y:3}..{y+9}: {rowsum[y:y+10].sum():5d}px  {'#'*(rowsum[y:y+10].sum()//80)}")
