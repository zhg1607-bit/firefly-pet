# -*- coding: utf-8 -*-
"""make_previews.py —— 生成验收预览：棋盘格 GIF + 帧采样对照图 + 表情包来源对照图（修正 m00504）。"""
import sys
import subprocess
import numpy as np
from PIL import Image, ImageDraw

sys.stdout.reconfigure(encoding="utf-8")

ROOT = r"D:\wd\deepseek-harness\default-workspace\dsh-pet-custom"
FFMPEG = ROOT + r"\.tools\ffmpeg-9.0.1-essentials_build\bin\ffmpeg.exe"
WORK = ROOT + r"\work"

# ---- 棋盘格底（2160x1215，45px 格）----
def checker(w, h, tile=45, c1=(220, 220, 220), c2=(196, 196, 196)):
    g = (np.indices((h, w)).sum(axis=0) // tile) % 2
    img = np.empty((h, w, 3), np.uint8)
    img[g == 0] = c1
    img[g == 1] = c2
    return img

chk = Image.fromarray(checker(2160, 1215), "RGB")
chk.save(WORK + r"\checker_2160.png")

# ---- GIF：step03 透明 webm 叠棋盘格 ----
for name in ["待机呼吸休闲", "点击回应-开心跃动"]:
    src = f"{ROOT}\\step03\\{name}.webm"
    out = f"{WORK}\\preview-{name}.gif"
    cmd = [FFMPEG, "-y", "-c:v", "libvpx-vp9", "-i", src, "-i", WORK + r"\checker_2160.png",
           "-filter_complex",
           "[1:v][0:v]overlay,fps=12,scale=480:270:flags=lanczos,split[s0][s1];"
           "[s0]palettegen=stats_mode=diff[p];[s1][p]paletteuse=dither=bayer:bayer_scale=4",
           "-loop", "0", out]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert p.returncode == 0, f"gif failed {name}: {p.stderr[-400:]}"
    print("GIF:", out)

# ---- 帧采样对照图 ----
def grab(src, t, w=2160, h=1215):
    tmp = WORK + r"\frame_tmp.png"
    cmd = [FFMPEG, "-y", "-v", "error", "-ss", str(t), "-c:v", "libvpx-vp9", "-i", src,
           "-frames:v", "1", tmp]
    p = subprocess.run(cmd, capture_output=True)
    assert p.returncode == 0, f"frame grab failed at t={t}: {p.stderr[:200]}"
    return np.asarray(Image.open(tmp).convert("RGBA")).astype(np.uint8)

names = ["待机呼吸休闲", "点击回应-开心跃动"]
times = [0, 2, 4, 6, 8]
TILE = 320
tile_h = int(TILE * 1215 / 2160)  # 180
pad = 8
sheet = Image.new("RGB", (len(times) * (TILE + pad) + pad,
                           len(names) * (tile_h + 28 + pad) + pad), (255, 255, 255))
d = ImageDraw.Draw(sheet)
for r, name in enumerate(names):
    for c, t in enumerate(times):
        fr = grab(f"{ROOT}\\step03\\{name}.webm", t)
        img = Image.fromarray(fr, "RGBA").resize((TILE, tile_h), Image.LANCZOS)
        tile = Image.new("RGBA", (TILE, tile_h), (0, 0, 0, 0))
        tile.paste(Image.fromarray(checker(TILE, tile_h, 15), "RGB"))
        tile.paste(img, (0, 0), img)
        x = pad + c * (TILE + pad)
        y = pad + r * (tile_h + 28 + pad)
        sheet.paste(tile.convert("RGB"), (x, y))
        d.text((x + 2, y + tile_h + 6), f"{'idle' if r == 0 else 'jump'} {t}s", fill=(40, 40, 40))
sheet.save(WORK + r"\preview_frames_sheet.png")
print("frames sheet:", WORK + r"\preview_frames_sheet.png")

# 表情包对照图已移到 tools\make_memes.py（区域定义与提取逻辑放在一起，避免两处不一致）

