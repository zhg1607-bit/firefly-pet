# -*- coding: utf-8 -*-
"""make_montage.py —— 把 step03 的所有动画做成一张「动作总览图」+ 体检表。

每个动画取 t≈中段的一帧，叠棋盘格，铺成网格（自动按数量算行列）。
同时用同款绿幕/包围盒算法做一次轻体检（绿色占比 / 角色包围盒），
输出 report/kling_20_montage.png 与 report/kling_20_probe.tsv。
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
FFMPEG = ROOT / ".tools" / "ffmpeg-9.0.1-essentials_build" / "bin" / "ffmpeg.exe"
STEP03 = ROOT / "step03"
TMP = ROOT / "work" / "_montage"
sys.stdout.reconfigure(encoding="utf-8")

TILE_W, TILE_H = 360, 240  # 缩略格尺寸（2160x1215 等比缩小）
AI_BACKUP = ROOT / "work" / "ai-video-backup"   # 可灵 AI 生成的那批原片（用来标来源）
# 「东张西望」的可灵原片生成了三个克隆人（生成事故），已用程序化版顶掉，不算 AI 片。
AI_REPLACED = {"东张西望"}


def checker(w, h, tile=24, c1=(226, 226, 226), c2=(200, 200, 200)):
    g = (np.indices((h, w)).sum(axis=0) // tile) % 2
    img = np.empty((h, w, 3), np.uint8)
    img[g == 0] = c1
    img[g == 1] = c2
    return Image.fromarray(img, "RGB")


def grab_mid(src, t=4.0):
    tmp = TMP / "f.png"
    p = subprocess.run([str(FFMPEG), "-y", "-v", "error", "-ss", str(t), "-c:v", "libvpx-vp9",
                        "-i", str(src), "-frames:v", "1", str(tmp)], capture_output=True, text=True)
    if p.returncode != 0:
        return None
    return np.asarray(Image.open(tmp).convert("RGBA")).astype(np.uint8)


def metrics(rgba):
    a = rgba.astype(np.int16)
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    fg = al > 60
    green = fg & (g > 120) & (g - r > 60) & (g - b > 60)
    ys, xs = np.nonzero(fg & ~green)
    if len(ys) < 50:
        return "nochar", 0, None
    return "ok", round(100.0 * green.mean(), 1), (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))


def main():
    # 用法：make_montage.py [输出前缀] [列数]   默认 kling_20 / 5 列
    prefix = sys.argv[1] if len(sys.argv) > 1 else "kling_20"
    files = sorted(STEP03.glob("*.webm"))
    if not files:
        raise SystemExit("step03 里没有 webm，先跑 run_pipeline.ps1")
    TMP.mkdir(parents=True, exist_ok=True)
    ai_names = ({p.stem for p in AI_BACKUP.glob("*.mp4")} - AI_REPLACED
                if AI_BACKUP.exists() else set())
    n = len(files)
    if len(sys.argv) > 2:
        cols = int(sys.argv[2])
    else:
        cols = max(5, round((n * TILE_H / TILE_W) ** 0.5))   # 让整张图接近 4:3
    rows = (n + cols - 1) // cols
    pad, label_h = 8, 22
    sheet = Image.new("RGB", (cols * (TILE_W + pad) + pad,
                              rows * (TILE_H + label_h + pad) + pad), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    rows_out = []
    for i, f in enumerate(files):
        name = f.stem
        fr = grab_mid(f)
        if fr is None:
            continue
        st, gp, bb = metrics(fr)
        im = Image.fromarray(fr, "RGBA").resize((TILE_W, TILE_H), Image.LANCZOS)
        tile = checker(TILE_W, TILE_H)
        tile.paste(im, (0, 0), Image.fromarray(fr[..., 3]).resize((TILE_W, TILE_H), Image.LANCZOS))
        r, c = divmod(i, cols)
        x = pad + c * (TILE_W + pad)
        y = pad + r * (TILE_H + label_h + pad)
        sheet.paste(tile, (x, y))
        is_ai = name in ai_names
        tag = ("★AI  " if is_ai else "程序化 ") + (("%s  %.0f%%绿" % (name, gp)) if bb else name)
        d.text((x, y + TILE_H + 4), tag, fill=(10, 60, 160) if is_ai else (110, 110, 110))
        rows_out.append((name, st, gp, bb, "可灵AI" if is_ai else "程序化"))
    out_png = ROOT / "report" / (prefix + "_montage.png")
    out_tsv = ROOT / "report" / (prefix + "_probe.tsv")
    sheet.save(out_png)
    with open(out_tsv, "w", encoding="utf-8") as fh:
        fh.write("动画\t来源\t状态\t绿幕占比%\t角色bbox(x0,y0,x1,y1)\n")
        for name, st, gp, bb, src_kind in rows_out:
            fh.write("%s\t%s\t%s\t%s\t%s\n" % (name, src_kind, st, gp,
                                               (("%d,%d,%d,%d" % bb) if bb else "-")))
    print("montage:", out_png, sheet.size)
    print("tsv:", out_tsv)
    bad = [r for r in rows_out if r[1] != "ok"]
    print("体检 %d 条，异常 %d 条" % (len(rows_out), len(bad)))
    for b in bad:
        print("  !!", b)


if __name__ == "__main__":
    main()
