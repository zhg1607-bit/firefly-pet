"""从「纯黑视频」生成精确水印 mask：亮度 > 阈值 = 水印像素（黑背景无干扰）

原理：让 AI 视频工具生成一段**纯黑背景**的视频，它会把自己那套水印原样盖在黑底上；
      黑底亮度≈0，于是「亮度 > 阈值」的像素就精确等于水印形状。得到的 mask 交给
      `watermark_step01.py`，即可把素材视频里的同一水印像素用邻近背景色填掉。

用法:
    python scripts/make_mask_black.py [黑视频] [输出.mkv] [亮度阈值]

默认:
    黑视频   work/black_10s.mp4      （用 tools/make_test_videos.py 可生成演示用黑视频）
    输出     video/watermark_mask_v5.mkv   （watermark_step01.py 只认这个名字）
    阈值     20

⚠️ 黑视频的**分辨率/帧率/时长必须 ≥ 素材视频**（本链固定 1280x720 / 24fps / 10s）。
   mask 帧数不足会让 watermark_step01 提前截断输出。

【本次交付相对上游的改动】① 黑视频路径与输出路径改为命令行参数（上游硬编码了作者本机路径）；
  ② 逐像素 Python 循环改为 numpy 向量化（原版 1280x720x240 帧要跑十几分钟）。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
FFMPEG = str(ROOT / ".tools" / "ffmpeg-9.0.1-essentials_build" / "bin" / "ffmpeg.exe")

W, H = 1280, 720
FPS = 24
DEFAULT_LUM_THRESH = 20
DEFAULT_BLACK = ROOT / "work" / "black_10s.mp4"
DEFAULT_OUT = ROOT / "video" / "watermark_mask_v5.mkv"


def read_exact(stream, n: int) -> bytes:
    """阻塞读满 n 字节（管道 read 可能部分返回，必须循环）。"""
    buf = b""
    while len(buf) < n:
        chunk = stream.read(n - len(buf))
        if not chunk:
            break
        buf += chunk
    return buf


def make_mask(black_video: Path, dst: Path, lum_thresh: int = DEFAULT_LUM_THRESH) -> int:
    if not black_video.exists():
        print(f"[错误] 找不到黑视频：{black_video}")
        return 1
    dst.parent.mkdir(parents=True, exist_ok=True)

    proc = subprocess.Popen(
        [FFMPEG, "-loglevel", "error", "-i", str(black_video),
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE)
    raw = dst.with_suffix(".raw")
    frame_size = W * H * 3
    frames = 0
    hit_px = 0
    with open(raw, "wb") as fw:
        while True:
            buf = read_exact(proc.stdout, frame_size)
            if len(buf) < frame_size:
                break
            rgb = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
            lum = rgb.mean(axis=2)                     # 向量化：整帧一次算完
            mask = np.where(lum > lum_thresh, 255, 0).astype(np.uint8)
            hit_px += int((mask == 255).sum())
            fw.write(mask.tobytes())
            frames += 1
    proc.stdout.close()
    proc.wait()

    if frames == 0:
        print("[错误] 未能从黑视频读到任何帧，请检查编码格式")
        return 1
    print(f"分析帧数: {frames}  水印像素/帧: {hit_px // max(frames,1)}  "
          f"（占比 {hit_px / max(frames,1) / (W*H) * 100:.2f}%）")
    if hit_px == 0:
        print("[警告] 没有检测到任何水印像素——阈值可能过高，或这段黑视频真的全黑（该工具无水印）。")

    enc = [FFMPEG, "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", str(raw), "-c:v", "ffv1", "-pix_fmt", "gray", str(dst)]
    if subprocess.run(enc).returncode != 0:
        raw.unlink(missing_ok=True)
        print("[错误] mask 编码失败")
        return 1
    raw.unlink(missing_ok=True)
    print(f"mask 已生成: {dst} ({dst.stat().st_size / 1024:.0f} KB)")
    return 0


def main() -> int:
    black = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_BLACK
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT
    thresh = int(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_LUM_THRESH
    print(f"黑视频: {black}\n输出:   {dst}\n阈值:   {thresh}")
    return make_mask(black, dst, thresh)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
