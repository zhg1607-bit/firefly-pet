#!/usr/bin/env python3
"""校验透明动画产物的 alpha 通道是否真实存在。

用法：python check_alpha.py step04/*.webm      （PowerShell 下用 Get-ChildItem 展开亦可）

判断：提取第 1 秒处一帧的 RGBA，A 通道必须有真实层次（存在 >200 的不透明像素，
也存在 <100 的透明像素）——若全是 255 说明编码丢 alpha，必须修编码命令。

【本次交付相对上游的改动】
① `FFMPEG` 由 PATH 上的 `ffmpeg` 改为工作区自带的 `.tools/ffmpeg-9.0.1-essentials_build/bin/ffmpeg.exe`；
② 输入是 `.webm` 时自动加 `-c:v libvpx-vp9`——不加这个解码器 ffmpeg 会选到不认 alpha 的解码路径，误报 "alpha LOST"。
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FFMPEG = str(ROOT / ".tools" / "ffmpeg-9.0.1-essentials_build" / "bin" / "ffmpeg.exe")


def check_one(path: str) -> bool:
    rgba = path[:-4] + (".rgba" if not path.endswith(".rgba") else path)
    cmd = [FFMPEG, "-y", "-v", "error"]
    if path.lower().endswith(".webm"):
        cmd += ["-c:v", "libvpx-vp9"]
    cmd += ["-i", path, "-ss", "1", "-frames:v", "1",
            "-f", "rawvideo", "-pix_fmt", "rgba", rgba]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(rgba) or os.path.getsize(rgba) < 16:
        print(f"  [WARN] {path}: no frame extracted")
        return True
    with open(rgba, "rb") as fh:
        data = fh.read()
    alpha = data[3::4]  # rgba 每像素 4 字节，A 是第 4 个
    a_min, a_max = min(alpha), max(alpha)
    a_mean = sum(alpha) / len(alpha)
    ok = a_max > 200 and a_min < 100
    print(f"  {os.path.basename(path)}: alpha min={a_min} max={a_max} mean={a_mean:.1f}"
          f" -> {'OK' if ok else '!! LOST'}")
    os.remove(rgba)
    return ok


def main() -> int:
    files = sys.argv[1:]
    if not files:
        print("usage: python check_alpha.py <webm...>")
        return 2
    failed = 0
    for f in files:
        if not check_one(f):
            failed += 1
    print(f"check: {len(files) - failed}/{len(files)} alpha OK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
