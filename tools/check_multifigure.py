# -*- coding: utf-8 -*-
"""check_multifigure.py —— 快速排查 AI 生成的「一帧里冒出多个角色」事故。

原理：绿幕片里前景 = 非绿像素。把前景做连通块标记，如果同一帧里出现
**多个面积都很大的块**（各自 > 最大块的 25%），基本就是模型把角色复制了几份。
正常角色（含披风/长发/道具）通常只有 1 个主块，零碎特效块都很小。

用法：
    python tools\\check_multifigure.py                # 查 video\\ 里全部 mp4
    python tools\\check_multifigure.py 东张西望 待机呼吸休闲
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
FFMPEG = ROOT / ".tools" / "ffmpeg-9.0.1-essentials_build" / "bin" / "ffmpeg.exe"
W, H = 640, 360
RATIO = 0.25          # 次大块 >= 最大块的这个比例才算「另一个角色」
MIN_BLOB = 0.004 * W * H   # 太小的块忽略（噪点/小道具）


def frames_of(src, fps=2):
    cmd = [str(FFMPEG), "-v", "error", "-i", str(src),
           "-vf", "fps=%d,scale=%d:%d" % (fps, W, H),
           "-pix_fmt", "rgb24", "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    n = len(raw) // (W * H * 3)
    if n == 0:
        return np.zeros((0, H, W, 3), np.uint8)
    return np.frombuffer(raw[:n * W * H * 3], np.uint8).reshape(n, H, W, 3)


def big_blobs(frame):
    a = frame.astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    green = (g > 120) & (g - r > 60) & (g - b > 60)
    fg = ~green
    if fg.sum() < 500:
        return 0, 0
    lab, k = ndimage.label(fg)
    if k == 0:
        return 0, 0
    sizes = np.bincount(lab.ravel())[1:]
    sizes = np.sort(sizes)[::-1]
    top = sizes[0]
    major = sizes[sizes >= max(top * RATIO, MIN_BLOB)]
    return top, len(major)


def main():
    names = sys.argv[1:]
    if names:
        files = [ROOT / "video" / (n + ".mp4") for n in names]
    else:
        files = sorted((ROOT / "video").glob("*.mp4"))
    print("检查 %d 个源片 ..." % len(files))
    hits = []
    for f in files:
        if not f.exists():
            print("  跳过（不存在）", f.name)
            continue
        fr = frames_of(f)
        worst, worst_n = 0, 0
        for i in range(fr.shape[0]):
            top, m = big_blobs(fr[i])
            if m > worst_n:
                worst_n, worst = m, i
        flag = "  <== 疑似多角色!" if worst_n >= 3 else ""
        print("  %-24s 帧数%3d  同帧最大主块数=%d (frame %d)%s"
              % (f.stem, fr.shape[0], worst_n, worst, flag))
        if worst_n >= 3:
            hits.append(f.stem)
    print()
    if hits:
        print("疑似多角色 %d 条：%s" % (len(hits), ", ".join(hits)))
    else:
        print("未发现多角色：全部 %d 条同帧主块数 < 3" % len(files))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
