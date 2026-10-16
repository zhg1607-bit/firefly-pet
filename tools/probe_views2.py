# -*- coding: utf-8 -*-
"""probe_views2.py —— 按颜色分类渲染三立绘：S=皮肤 H=银发 D=深色服饰 E=眼睛/蓝紫 M=薄荷 O=橙 . =透明。"""
import sys
import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")

SRC = r"D:\wd\deepseek-harness\default-workspace\dsh-pet-custom\character\reference.png"
a = np.asarray(Image.open(SRC).convert("RGBA")).astype(int)
rgb = a[:, :, :3]
alpha = a[:, :, 3]


def classify(px):
    r, g, b = px
    if r > 225 and g > 220 and b > 205 and (r - g) > 10:  # 粉调皮肤
        return "S"
    if abs(r - g) < 9 and abs(g - b) < 9 and r > 190:  # 银灰发
        return "H"
    if b > 200 and r < 170 and g > 120:  # 蓝系（眼睛/缎带）
        return "E"
    if r < 90 and g < 90:  # 深色服饰
        return "D"
    if g > 130 and b > 120 and g > r + 25:  # 薄荷/青绿
        return "M"
    if r > 200 and g > 110 and g < 190 and b < 120:  # 橙
        return "O"
    return "x"


def render(x0, x1, y0, y1, cols=64, rows=40, title=""):
    print(f"=== {title} ===")
    for r in range(rows):
        line = ""
        for c in range(cols):
            ys = y0 + r * (y1 - y0) // rows
            ye = y0 + (r + 1) * (y1 - y0) // rows
            xs = x0 + c * (x1 - x0) // cols
            xe = x0 + (c + 1) * (x1 - x0) // cols
            m = alpha[ys:ye, xs:xe] > 16
            if not m.any():
                line += "."
                continue
            sub = rgb[ys:ye, xs:xe][m].mean(axis=0).round(0).astype(int)
            line += classify(sub)
        print(line)


render(38, 388, 19, 400, 64, 36, "左块")
render(474, 807, 19, 400, 64, 36, "中块")
render(818, 1158, 21, 400, 64, 36, "右块")
