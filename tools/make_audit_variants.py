#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
生成即梦审核诊断用的形象图变体（都输出 1280x720 纯绿底首帧图）
------------------------------------------------------------------
  work/char_longskirt_frame.png  长裙版：把短裙下摆向下延伸盖住过膝长筒袜，只留靴子
  复用已有的 work/char_nolegs_frame.png（上一轮网页端实验产物，若存在则校验）

用法：python tools/make_audit_variants.py
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
CHAR = ROOT / "character"
WORK = ROOT / "work"
GREEN = (0, 255, 0)


def load_figure():
    im = Image.open(CHAR / "front_stand.png").convert("RGBA")
    a = np.array(im)
    a[a[:, :, 3] >= 200, 3] = 255
    a[a[:, :, 3] < 200, 3] = 0
    return a


def class_masks(a):
    r = a[:, :, 0].astype(int)
    g = a[:, :, 1].astype(int)
    b = a[:, :, 2].astype(int)
    op = a[:, :, 3] > 0
    lum = (0.299 * r + 0.587 * g + 0.114 * b)
    sat = np.max(a[:, :, :3], axis=2).astype(int) - np.min(a[:, :, :3], axis=2).astype(int)
    skin = op & (r > 232) & (g > 198) & (g < 250) & (b > 172) & (b < 242)
    dark = op & (lum < 95)
    # 浅绿/薄荷色的裙摆与披风内衬：必须明显偏绿（银白发 r≈g≈b 会被这个条件排除）
    skirt = op & (lum > 150) & (g - r >= 10) & (g - b >= 6) & ~skin
    return op, skin, dark, skirt, lum


def analyze(a):
    op, skin, dark, skirt, lum = class_masks(a)
    h = a.shape[0]
    print(f"figure {a.shape[1]}x{h}")
    print("  y     opaque skin dark skirt")
    for y in range(0, h, 12):
        print(f"  {y:>4}  {op[y].sum():>5} {skin[y].sum():>4} {dark[y].sum():>4} {skirt[y].sum():>5}")
    return op, skin, dark, skirt


def find_hem_and_boots(a):
    """裙摆下沿 = 下半身最后一个「偏绿裙摆」较多的行；靴顶 = 底部固定的 42px（靴子+鞋底）"""
    op, skin, dark, skirt, lum = class_masks(a)
    h = a.shape[0]
    rows_skirt = [y for y in range(int(h * 0.45), h) if skirt[y].sum() > 12]
    hem = max(rows_skirt) if rows_skirt else int(h * 0.62)
    boot_top = h - 42
    return hem, boot_top


def make_longskirt(a, hem, boot_top):
    out = a.copy()
    h, w = a.shape[:2]
    op, skin, dark, skirt, lum = class_masks(a)
    # 延伸基色 = 裙摆下沿以上 45 行内「被判为裙摆」的像素均值
    band = slice(max(0, hem - 45), hem + 1)
    m = skirt[band]
    if m.any():
        base = a[band, :, :3][m].mean(axis=0)
    else:
        base = np.array([207, 232, 200], dtype=float)
    base = np.array(base, dtype=float)
    print(f"  延伸基色 = RGB({int(base[0])},{int(base[1])},{int(base[2])})  hem={hem}  boot_top={boot_top}"
          f"  取样像素={int(m.sum())}")
    filled = 0
    for y in range(hem + 1, min(boot_top, h)):
        k = (y - hem) / max(1, (boot_top - hem))
        col = np.clip(base * (1.0 - 0.10 * k), 0, 255)
        rows = out[y, :, 3] > 0
        # 只覆盖「腿」的颜色（深色长筒袜 / 皮肤 / 亮色袜口），保留完全透明的像素
        out[y, rows, 0] = col[0]
        out[y, rows, 1] = col[1]
        out[y, rows, 2] = col[2]
        filled += int(rows.sum())
    print(f"  覆盖像素 = {filled}")
    return out


def to_frame(a, dst):
    """贴到 1280x720 纯绿画布：头顶 20%(y=144)、脚底 85%(y=612)、水平居中"""
    fig_h, fig_w = a.shape[:2]
    s = (612 - 144) / fig_h
    nw, nh = max(1, round(fig_w * s)), round(fig_h * s)
    im = Image.fromarray(a).resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGBA", (1280, 720), GREEN + (255,))
    canvas.alpha_composite(im, ((1280 - nw) // 2, 144))
    canvas.convert("RGB").save(dst)
    # 统计绿占比与角色 bbox
    arr = np.array(canvas.convert("RGB")).astype(int)
    isg = (arr[:, :, 0] < 60) & (arr[:, :, 1] > 200) & (arr[:, :, 2] < 60)
    ys, xs = np.where(~isg)
    print(f"  -> {dst.name}  {nw}x{nh} at x{(1280-nw)//2} y144  green={100*isg.mean():.2f}%  "
          f"bbox x{xs.min()}..{xs.max()} y{ys.min()}..{ys.max()}")


def main():
    a = load_figure()
    op, skin, dark, skirt = analyze(a)
    hem, boot_top = find_hem_and_boots(a)
    ls = make_longskirt(a, hem, boot_top)
    to_frame(ls, WORK / "char_longskirt_frame.png")
    nl = WORK / "char_nolegs_frame.png"
    if nl.exists():
        im = Image.open(nl)
        print(f"已有 {nl.name} {im.size}")
    else:
        print("!! work/char_nolegs_frame.png 不存在，需要重建")


if __name__ == "__main__":
    main()
