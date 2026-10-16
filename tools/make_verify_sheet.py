# -*- coding: utf-8 -*-
"""把 step04 的透明 webm 抽帧、叠到棋盘格上，并与原视频同帧并排，生成一张对比图。

用法: python make_verify_sheet.py [工程根目录]
产物: work/verify_sheet.png
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
FFMPEG = str(ROOT / ".tools" / "ffmpeg-9.0.1-essentials_build" / "bin" / "ffmpeg.exe")
N = 60  # 抽第 60 帧


def grab(src: Path, frame: int, dst: Path, decode_vp9: bool = False) -> bool:
    cmd = [FFMPEG, "-y", "-loglevel", "error"]
    if decode_vp9:
        cmd += ["-c:v", "libvpx-vp9"]
    cmd += ["-i", str(src), "-vf", f"select=eq(n\\,{frame})", "-vframes", "1", str(dst)]
    return subprocess.run(cmd).returncode == 0


def checker(w: int, h: int, size: int = 24) -> Image.Image:
    im = Image.new("RGB", (w, h), (58, 58, 64))
    d = ImageDraw.Draw(im)
    for y in range(0, h, size):
        for x in range(0, w, size):
            if (x // size + y // size) % 2:
                d.rectangle([x, y, x + size - 1, y + size - 1], fill=(78, 78, 86))
    return im


def main() -> int:
    work = ROOT / "work"
    work.mkdir(exist_ok=True)
    tiles = []

    src0 = ROOT / "video" / "test-stand.mp4"
    src1 = ROOT / "step01" / "test-stand.mp4"
    src2 = ROOT / "step02" / "test-stand.webm"
    src3 = ROOT / "step04" / "test-stand.webm"

    for i, (src, vp9, label) in enumerate([
        (src0, False, "① 原始绿幕视频（右下角带模拟水印）"),
        (src1, False, "② step01 去水印后（水印已被邻近背景色填充）"),
        (src2, True, "③ step02 绿幕抠像后（叠棋盘格看 alpha）"),
        (src3, True, "④ step04 最终缩略图 640x360（叠棋盘格）"),
    ]):
        if not src.exists():
            print(f"跳过（不存在）：{src}")
            continue
        raw = work / f"_v{i}.png"
        if not grab(src, N, raw, vp9):
            print(f"抽帧失败：{src}")
            continue
        im = Image.open(raw).convert("RGBA")
        W, H = im.size
        bg = checker(W, H).convert("RGBA")
        bg.alpha_composite(im)
        d = ImageDraw.Draw(bg)
        d.rectangle([0, 0, W, 26], fill=(20, 20, 24, 220))
        d.text((8, 7), label, fill=(255, 255, 255))
        tiles.append(bg.convert("RGB"))
        raw.unlink(missing_ok=True)

    if not tiles:
        print("没有可用的帧")
        return 1
    scale = 2
    tiles = [t.resize((t.width * scale, t.height * scale), Image.NEAREST) for t in tiles]
    cols = 2
    rows = (len(tiles) + cols - 1) // cols
    cw = max(t.width for t in tiles)
    ch = max(t.height for t in tiles)
    sheet = Image.new("RGB", (cw * cols + 30, ch * rows + 30), (16, 16, 18))
    for i, t in enumerate(tiles):
        x = (i % cols) * (cw + 10) + 10
        y = (i // cols) * (ch + 10) + 10
        sheet.paste(t, (x, y))
    out = work / "verify_sheet.png"
    sheet.save(out)
    print(f"对比图: {out}  ({sheet.width}x{sheet.height})")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
