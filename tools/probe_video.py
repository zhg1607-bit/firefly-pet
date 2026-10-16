# -*- coding: utf-8 -*-
"""probe_video.py —— 对绿幕原始视频做体检：规格 / 绿幕占比 / 角色包围盒 / 运动量 / 配色。

用法：python tools/probe_video.py <video.mp4> [采样帧数]
依赖 ffmpeg（脚本内硬编码路径）+ PIL + numpy。
输出人类可读报告到 stdout。
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
FFDIR = ROOT / ".tools" / "ffmpeg-9.0.1-essentials_build" / "bin"
FFMPEG = FFDIR / "ffmpeg.exe"
FFPROBE = FFDIR / "ffprobe.exe"
TMP = ROOT / "work" / "_probe"
sys.stdout.reconfigure(encoding="utf-8")


def probe(path):
    p = subprocess.run([str(FFPROBE), "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height,r_frame_rate,nb_frames",
                        "-show_entries", "format=duration",
                        "-of", "json", str(path)], capture_output=True, text=True)
    d = json.loads(p.stdout or "{}")
    st = (d.get("streams") or [{}])[0]
    return st.get("width"), st.get("height"), st.get("r_frame_rate"), st.get("nb_frames"), float(d.get("format", {}).get("duration", 0) or 0)


def sample_frames(path, n, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    for f in outdir.glob("f*.png"):
        f.unlink()
    fps = max(0.25, round(n / 10.0, 2))
    p = subprocess.run([str(FFMPEG), "-y", "-v", "error", "-i", str(path),
                        "-vf", "fps=%s" % fps,
                        str(outdir / "f%03d.png")], capture_output=True, text=True)
    return sorted(outdir.glob("f*.png")), (p.stderr or "")[-400:]


def analyze(img_path):
    im = Image.open(img_path).convert("RGB")
    a = np.asarray(im).astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    green = (g > 120) & (g - r > 60) & (g - b > 60)
    fg = ~green
    if fg.sum() < 50:
        return {"green_pct": 100.0, "bbox": None, "px": 0}
    ys, xs = np.nonzero(fg)
    bbox = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    px = fg & (np.abs(a[..., 0] - a[..., 1]) + np.abs(a[..., 1] - a[..., 2]) + np.abs(a[..., 0] - a[..., 2]) > 24)
    pal = {}
    if px.sum() > 100:
        q = (a[px] // 32 * 32)
        for c in map(tuple, q):
            pal[c] = pal.get(c, 0) + 1
    top = sorted(pal.items(), key=lambda kv: -kv[1])[:8]
    return {"green_pct": round(100.0 * green.mean(), 2), "bbox": bbox, "h": bbox[3] - bbox[1],
            "w": bbox[2] - bbox[0], "cx": (bbox[0] + bbox[2]) // 2, "cy": (bbox[1] + bbox[3]) // 2,
            "palette": [("%d,%d,%d" % c, round(100.0 * n / px.sum(), 1)) for c, n in top]}


def main():
    path = Path(sys.argv[1])
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    w, h, fr, nbf, dur = probe(path)
    print("file:", path.name)
    print("spec: %sx%s @%s  frames=%s  dur=%.3fs  size=%.1f MB" % (w, h, fr, nbf, dur, path.stat().st_size / 1048576))
    frames, err = sample_frames(path, n, TMP)
    print("sampled %d frames" % len(frames))
    prev = None
    d0 = None
    motions = []
    for i, f in enumerate(frames):
        r = analyze(f)
        if i == 0:
            d0 = r
            print("  f0 : green=%s%% bbox=%s (%sx%s) cx=%s cy=%s" % (r["green_pct"], r["bbox"], r.get("w"), r.get("h"), r.get("cx"), r.get("cy")))
            print("       palette:", r.get("palette"))
        else:
            print("  f%-3d: green=%s%% bbox=%s (%sx%s) cx=%s cy=%s" % (i, r["green_pct"], r["bbox"], r.get("w"), r.get("h"), r.get("cx"), r.get("cy")))
        im = np.asarray(Image.open(f).convert("RGB")).astype(np.int16)
        if prev is not None:
            motions.append(float(np.abs(im - prev).mean()))
        prev = im
    if motions:
        print("motion (mean |Δ| between adjacent samples): min=%.2f avg=%.2f max=%.2f" % (min(motions), sum(motions) / len(motions), max(motions)))
    # 首尾帧一致性
    if len(frames) >= 2:
        a = np.asarray(Image.open(frames[0]).convert("RGB")).astype(np.int16)
        b = np.asarray(Image.open(frames[-1]).convert("RGB")).astype(np.int16)
        print("first-vs-last mean |Δ| = %.2f" % np.abs(a - b).mean())


if __name__ == "__main__":
    main()
