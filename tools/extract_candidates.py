# -*- coding: utf-8 -*-
"""把设定表「表情参考」区里的候选头像全部裁出来，供用户挑选 4 张做表情包。

做法（关键教训）：参考图 RGBA 的背景是**透明**的（RGB 显示为纯黑），
表情头像直接坐在透明背景上 —— 正确做法是直接用 alpha 通道裁剪，
不要用颜色/洪水填充去抠白底（会把银白发 250+ 的高光当成背景吃掉）。

用法: python tools/extract_candidates.py
产物: work/meme_candidates/cand-<编号>.png + work/meme_candidates_sheet.png（带编号对照图）
      report/meme_candidates.txt（每张的不透明占比，供筛选）
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "character" / "reference.png"
STRIP_Y0, STRIP_Y1 = 400, 845  # 表情参考行在原图里的纵向范围

# 候选区域（strip 坐标：x0,y0,x1,y1）。行 1 = y138-266 的 7 块；行 2 = y292-414 的 4 块。
CANDIDATES = [
    ("01", 24, 138, 164, 266),
    ("02", 181, 138, 325, 266),
    ("03", 340, 138, 484, 266),
    ("04", 515, 138, 723, 376),
    ("05", 728, 138, 911, 367),
    ("06", 944, 138, 1097, 265),
    ("07", 1110, 138, 1264, 266),
    ("08", 24, 292, 138, 413),
    ("09", 155, 292, 258, 413),
    ("10", 277, 292, 374, 414),
    ("11", 392, 292, 490, 414),
]
MARGIN = 6


def main() -> int:
    im = Image.open(REF).convert("RGBA")
    outdir = ROOT / "work" / "meme_candidates"
    outdir.mkdir(parents=True, exist_ok=True)
    a = np.asarray(im)
    tiles = []
    report = []
    for num, x0, y0, x1, y1 in CANDIDATES:
        y0a, y1a = y0 + STRIP_Y0, y1 + STRIP_Y0
        box = (max(0, x0 - MARGIN), max(0, y0a - MARGIN),
               min(im.width, x1 + MARGIN), min(im.height, y1a + MARGIN))
        tile = im.crop(box)
        # 若角落是不透明近白（卡片底），floodfill 洗掉连到边框的部分；透明底则不动
        alpha = np.asarray(tile.getchannel("A"))
        rgb = np.asarray(tile.convert("RGB"))
        corners = [(2, 2), (tile.width - 3, 2), (2, tile.height - 3), (tile.width - 3, tile.height - 3)]
        if any(alpha[y, x] > 200 and rgb[y, x].min() > 240 for x, y in corners):
            for seed in corners:
                ImageDraw.floodfill(tile, seed, (0, 0, 0, 0), thresh=40)
        p = outdir / f"cand-{num}.png"
        tile.save(p)
        alpha2 = np.asarray(tile.getchannel("A"))
        opaque = float((alpha2 > 200).mean())
        report.append(f"cand-{num}  {tile.width}x{tile.height}  不透明占比 {opaque:.0%}")
        tiles.append(tile)

    # 编号对照图
    n = len(tiles)
    cols = 4
    rows = (n + cols - 1) // cols
    cw = max(t.width for t in tiles) + 8
    ch = max(t.height for t in tiles) + 26
    sheet = Image.new("RGBA", (cols * cw + 8, rows * ch + 8), (40, 40, 52, 255))
    d = ImageDraw.Draw(sheet)
    for i, t in enumerate(tiles):
        cx, cy = 8 + (i % cols) * cw, 8 + (i // cols) * ch
        sheet.alpha_composite(t, (cx + (cw - 8 - t.width) // 2, cy + 24 + (ch - 26 - t.height) // 2))
        d.rectangle([cx, cy, cx + cw - 8, cy + 22], fill=(30, 30, 40, 255))
        d.text((cx + 4, cy + 4), f"cand-{CANDIDATES[i][0]}", fill=(255, 255, 255, 255))
    sheet.convert("RGB").save(ROOT / "work" / "meme_candidates_sheet.png")

    rep = ROOT / "report" / "meme_candidates.txt"
    rep.write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    print(f"对照图: {ROOT / 'work' / 'meme_candidates_sheet.png'}")
    print(f"报告:   {rep}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
