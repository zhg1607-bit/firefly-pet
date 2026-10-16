#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
把任意「绿幕背景 + 角色」的图，规整成 1280x720 基准首帧
------------------------------------------------------------
- 背景判定：g - max(r,b) > 40 且 g > 140 —— 兼容 AI 生成的不纯绿
- 背景统一量化成纯 #00FF00（去掉 JPEG 噪点/渐变）
- 角色等比缩放到「高度 = 画面 65%」，头顶贴到 20%(y=144)、水平居中 x=640
- 边缘做 1px 羽化，避免硬锯齿

用法：python tools/fit_green_frame.py <输入图> [输出png] [--keep-scale]
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

sys.stdout.reconfigure(encoding="utf-8")

W, H = 1280, 720
HEAD_Y = 144          # 头顶 = 20%
FEET_Y = 612          # 脚底 = 85%
CX = W // 2
GREEN = np.array([0, 255, 0], dtype=np.uint8)


def bg_mask(arr):
    r = arr[:, :, 0].astype(int)
    g = arr[:, :, 1].astype(int)
    b = arr[:, :, 2].astype(int)
    return (g - np.maximum(r, b) > 40) & (g > 140)


def bbox_of(mask):
    ys, xs = np.where(mask)
    if len(ys) == 0:
        raise SystemExit("图里找不到角色（全部被判成背景）")
    return xs.min(), ys.min(), xs.max(), ys.max()


def main():
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith("--") \
        else src.with_name(src.stem + "_frame1280.png")
    im = Image.open(src).convert("RGB")
    arr = np.array(im)
    bg = bg_mask(arr)
    print(f"输入 {src.name} {im.width}x{im.height}  背景占比 {100*bg.mean():.2f}%")
    x0, y0, x1, y1 = bbox_of(~bg)
    fw, fh = x1 - x0 + 1, y1 - y0 + 1
    print(f"角色 bbox x{x0}..{x1} y{y0}..{y1}  {fw}x{fh}")

    # 抠出来（背景填绿）
    fig = arr.copy()
    fig[bg] = GREEN
    fig_im = Image.fromarray(fig).crop((x0, y0, x1 + 1, y1 + 1))

    s = (FEET_Y - HEAD_Y) / fh
    nw, nh = max(1, round(fw * s)), max(1, round(fh * s))
    fig_im = fig_im.resize((nw, nh), Image.LANCZOS)
    # 缩放后重新量化背景，去掉插值产生的杂色
    a2 = np.array(fig_im)
    fig_im = Image.fromarray(np.where(bg_mask(a2)[:, :, None], GREEN, a2).astype(np.uint8))

    # 1px 羽化alpha：把背景变透明再合成，边缘更干净
    a3 = np.array(fig_im)
    alpha = np.where(bg_mask(a3), 0, 255).astype(np.uint8)
    alpha_im = Image.fromarray(alpha).filter(ImageFilter.GaussianBlur(0.6))
    canvas = Image.new("RGB", (W, H), tuple(GREEN))
    px = (CX - nw // 2, HEAD_Y)
    canvas.paste(fig_im, px, alpha_im)
    # 最后把画布上「接近绿」的像素全部推成纯绿
    c = np.array(canvas)
    c[bg_mask(c)] = GREEN
    Image.fromarray(c).save(dst)

    final_bg = bg_mask(c)
    ys, xs = np.where(~final_bg)
    print(f"输出 {dst.name} 1280x720  绿底占比 {100*final_bg.mean():.2f}%  "
          f"角色 bbox x{xs.min()}..{xs.max()} y{ys.min()}..{ys.max()}  "
          f"缩放 {s:.4f} 尺寸 {nw}x{nh}")
    print(f"  头顶应≈{HEAD_Y} 实际 {ys.min()}，脚底应≈{FEET_Y} 实际 {ys.max()}，中心应≈{CX} 实际 {(xs.min()+xs.max())//2}")


if __name__ == "__main__":
    main()
