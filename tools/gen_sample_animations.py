# -*- coding: utf-8 -*-
"""gen_sample_animations.py —— 用提取的正面立绘合成两段 10 秒绿幕示例动画：
1) 待机呼吸休闲（呼吸起伏 + 轻微缩放）
2) 点击回应-开心跃动（连续小跳 + 起跳蹲伏/落地压扁）
规格与提示词强制约束一致：1280x720 / 24fps / 纯绿 #00FF00 / 头顶 20% / 脚底 85% / 居中 / 首尾帧一致。
输出 video/<动画名>.mp4（文件名 = 插件内置动画名，零配置覆盖）。"""
import sys
import subprocess
import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")

ROOT = r"D:\wd\deepseek-harness\default-workspace\dsh-pet-custom"
FFMPEG = ROOT + r"\.tools\ffmpeg-9.0.1-essentials_build\bin\ffmpeg.exe"

W, H, FPS, DUR = 1280, 720, 24, 10.0
N = int(FPS * DUR)
GREEN = (0, 255, 0)          # 纯绿幕
HEAD_LINE = int(H * 0.20)    # 头顶线 144
FEET_LINE = int(H * 0.85)    # 脚底线 612
CX = W // 2                  # 640

fig = np.asarray(Image.open(ROOT + r"\character\front_stand.png").convert("RGBA")).astype(np.float32)
frgb, fa = fig[:, :, :3], fig[:, :, 3]
fa = np.clip(fa, 0, 255)
fa[fa >= 200] = 255.0        # 原图内部 alpha=253，归一化避免透绿
fig_h, fig_w = fa.shape

S0 = (FEET_LINE - HEAD_LINE) / fig_h  # 头顶 20% 脚底 85% → 缩放
print(f"figure {fig_w}x{fig_h}, S0 = {S0:.4f}")

canvas = np.zeros((H, W, 3), np.uint8)
canvas[:] = GREEN

def render(yoff, sx, sy):
    """脚底锚点 (CX, FEET_LINE)，向上偏移 yoff，水平/垂直压扁 sx/sy。"""
    w = max(1, int(fig_w * S0 * sx))
    h = max(1, int(fig_h * S0 * sy))
    r = np.asarray(Image.fromarray(np.dstack([frgb, fa]).astype(np.uint8), "RGBA")
                   .resize((w, h), Image.LANCZOS)).astype(np.float32)
    rf, ra = r[:, :, :3], r[:, :, 3] / 255.0
    ra3 = ra[:, :, None]
    x0 = CX - w // 2
    y0 = int(FEET_LINE - yoff) - h
    y0 = max(0, min(H - h, y0))
    x0 = max(0, min(W - w, x0))
    frame = canvas.copy().astype(np.float32)
    frame[y0:y0 + h, x0:x0 + w] = rf * ra3 + GREEN * (1 - ra3)
    return frame.astype(np.uint8)

def encode(frames, out):
    cmd = [FFMPEG, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264", "-crf", "18",
           "-pix_fmt", "yuv420p", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in frames:
        p.stdin.write(f.tobytes())
    p.stdin.close()
    assert p.wait() == 0, f"ffmpeg failed: {out}"
    print(f"written {out}")

# ---------- 待机呼吸休闲 ----------
T_BREATH = DUR / 3  # 3 个呼吸周期，首尾同相位
idle_frames = []
for i in range(N):
    t = i / FPS
    pose_t = 0.0 if i == N - 1 else t  # 强制末帧 = 首帧
    yoff = -9.0 * np.sin(2 * np.pi * pose_t / T_BREATH)
    s = S0 * (1 + 0.012 * np.sin(2 * np.pi * pose_t / T_BREATH - np.pi / 2))
    idle_frames.append(render(yoff, 1.0, s / S0))
encode(idle_frames, ROOT + r"\video\待机呼吸休闲.mp4")

# ---------- 点击回应-开心跃动 ----------
# (起跳时刻, 滞空时长, 峰值高度px)
hops = [(0.9, 0.50, 50), (2.0, 0.55, 80), (3.4, 1.50, 120), (5.6, 0.55, 70),
        (6.9, 0.45, 40), (8.0, 0.50, 55)]

def pose(t):
    yoff, sx, sy = 0.0, 1.0, 1.0
    for t0, dur, hmax in hops:
        if t0 - 0.12 <= t < t0:               # 起跳前蹲伏
            u = (t - (t0 - 0.12)) / 0.12
            sy = 1.0 - 0.06 * u
            sx = 1.0 + 0.04 * u
            return yoff, sx, sy
        if t0 <= t < t0 + dur:                # 抛物线滞空
            u = (t - t0) / dur
            yoff = 4 * hmax * u * (1 - u)
            return yoff, sx, sy
        if t0 + dur <= t < t0 + dur + 0.15:   # 落地压扁
            u = (t - t0 - dur) / 0.15
            sy = 0.90 + 0.10 * u
            sx = 1.08 - 0.08 * u
            return yoff, sx, sy
    return 0.0, 1.0, 1.0

jump_frames = []
for i in range(N):
    t = i / FPS
    yoff, sx, sy = pose(t)
    jump_frames.append(render(yoff, sx, sy))
encode(jump_frames, ROOT + r"\video\点击回应-开心跃动.mp4")
