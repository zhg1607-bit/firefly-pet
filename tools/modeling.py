#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""流萤桌宠 · 建模工具链

把「建模」需要的四种能力封装成命令行工具，供后续会话复用：

  1) extract   —— 从任意背景抠出角色（GrabCut + 导向滤波精修 + 羽化），
                  复杂渐变背景也能抠，弥补纯泛洪填充的不足
  2) vectorize —— 彩色矢量化（vtracer），产出可无限缩放的 SVG
  3) rasterize —— SVG 光栅化（Edge headless），用于验证矢量结果
  4) compare   —— 客观比对（SSIM / PSNR / 不透明区 IoU / 色差），
                  在没有视觉能力时充当"眼睛"
  5) upscale   —— 高质量放大（LANCZOS + 非锐化掩模）
  6) transplant—— 无缝移植（Poisson 融合），把某个部件/五官贴到另一张图上
  7) inpaint   —— 修补缺口

用法示例：
  python modeling.py extract   assets/firefly.png build/out.png
  python modeling.py vectorize assets/stand.png build/stand.svg --colors 12
  python modeling.py rasterize build/stand.svg build/stand-render.png --width 916
  python modeling.py compare   assets/stand.png build/stand-render.png
  python modeling.py upscale   assets/firefly.png build/big.png --factor 2
  python modeling.py transplant base.png face.png out.png --box 100,200,80,60

依赖：opencv-contrib-python-headless, scikit-image, scipy, numpy, Pillow, vtracer
"""
import argparse
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageFilter

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None

EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "msedge",
]


def die(msg):
    print("[x] " + msg)
    sys.exit(1)


def load_rgba(path):
    return np.asarray(Image.open(path).convert("RGBA"))


def save_rgba(arr, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    Image.fromarray(arr.astype(np.uint8), "RGBA").save(path)
    print("[ok] 已保存 %s (%dx%d)" % (path, arr.shape[1], arr.shape[0]))


def largest_component(mask):
    """保留最大连通域，去掉抠像残留的碎块。"""
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    if n <= 1:
        return mask
    idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return (lab == idx).astype(np.uint8)


def fill_holes(mask):
    """填内部空洞（先补边再泛洪求背景）。"""
    h, w = mask.shape
    pad = cv2.copyMakeBorder(mask, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0)
    flood = pad.copy()
    cv2.floodFill(flood, np.zeros((pad.shape[0] + 2, pad.shape[1] + 2), np.uint8), (0, 0), 1)
    holes = (flood[1:-1, 1:-1] == 0).astype(np.uint8)
    return np.clip(mask + holes, 0, 1).astype(np.uint8)


# ----------------------------------------------------------------------
# 1) extract：抠像
# ----------------------------------------------------------------------
def border_bg_model(rgb, margin=0.06, k=3):
    """用图像边框环估计背景色模型（k 个聚类中心），对渐变背景也稳健。"""
    h, w = rgb.shape[:2]
    m = max(2, int(min(h, w) * margin))
    ring = np.concatenate([
        rgb[:m, :, :].reshape(-1, 3),
        rgb[-m:, :, :].reshape(-1, 3),
        rgb[:, :m, :].reshape(-1, 3),
        rgb[:, -m:, :].reshape(-1, 3),
    ]).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, _, centers = cv2.kmeans(ring, k, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
    return centers, ring


def flood_bg(rgb, tol):
    """从四边做浮动容差泛洪，返回前景掩膜（适合纯色/渐变等简单背景）。"""
    h, w = rgb.shape[:2]
    img = rgb.copy()
    mask = np.zeros((h + 2, w + 2), np.uint8)
    flags = 4 | (255 << 8) | cv2.FLOODFILL_MASK_ONLY
    step_x = max(1, w // 16)
    step_y = max(1, h // 16)
    for x in range(0, w, step_x):
        cv2.floodFill(img, mask, (x, 0), 0, (tol,) * 3, (tol,) * 3, flags)
        cv2.floodFill(img, mask, (x, h - 1), 0, (tol,) * 3, (tol,) * 3, flags)
    for y in range(0, h, step_y):
        cv2.floodFill(img, mask, (0, y), 0, (tol,) * 3, (tol,) * 3, flags)
        cv2.floodFill(img, mask, (w - 1, y), 0, (tol,) * 3, (tol,) * 3, flags)
    bg = mask[1:-1, 1:-1] > 0
    fg = (~bg).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    return largest_component(fg)


def saliency_fg(rgb):
    """显著性检测 + 中心先验（角色居中的立绘/截图场景）。"""
    try:
        sal = cv2.saliency.StaticSaliencySpectralResidual_create()
        ok, smap = sal.computeSaliency(rgb)
        if not ok:
            return None
        smap = cv2.normalize(smap, None, 0, 1, cv2.NORM_MINMAX).astype(np.float32)
        h, w = smap.shape[:2]
        # 中心先验：越靠画面中心权重越高（这类图里角色几乎总在中间）
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        sig = 0.38 * min(h, w)
        prior = np.exp(-(((xx - w / 2.0) ** 2 + (yy - h / 2.0) ** 2) / (2 * sig * sig)))
        comb = cv2.normalize(smap * (0.35 + 0.65 * prior), None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        comb = cv2.GaussianBlur(comb, (0, 0), 3)
        _, th = cv2.threshold(comb, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        fg = (th > 0).astype(np.uint8)
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8))
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        return fill_holes(largest_component(fg))
    except Exception as exc:  # pragma: no cover
        print("[!] 显著性检测不可用：%s" % exc)
        return None


def grabcut_refine(rgb, init, iters, erode, dilate):
    """以掩膜方式跑 GrabCut 精修（init=1 为前景）。"""
    h, w = rgb.shape[:2]
    gm = np.full((h, w), cv2.GC_PR_BGD, np.uint8)
    gm[init == 1] = cv2.GC_PR_FGD
    core = cv2.erode(init, np.ones((5, 5), np.uint8), iterations=max(1, erode))
    gm[core == 1] = cv2.GC_FGD
    far = cv2.dilate(init, np.ones((5, 5), np.uint8), iterations=max(1, dilate))
    gm[far == 0] = cv2.GC_BGD
    bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(rgb, gm, None, bgd, fgd, iters, cv2.GC_INIT_WITH_MASK)
    m = np.where((gm == cv2.GC_FGD) | (gm == cv2.GC_PR_FGD), 1, 0).astype(np.uint8)
    return largest_component(m)


def refine_alpha(rgb, m, radius, eps, feather):
    """边缘精修 + 羽化。两个坑都兜住：
    OpenCV 5 的 guidedFilter 走 uint8 会返回全 0（改用 float32），
    float32 下 eps 过小会产生 NaN（nan_to_num + 结果校验）。"""
    alpha = (m * 255).astype(np.uint8)
    if radius > 0:
        try:
            guide = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
            src = alpha.astype(np.float32) / 255.0
            out = cv2.ximgproc.guidedFilter(guide, src, radius, max(eps, 1e-3))
            out = np.nan_to_num(out, nan=0.0, posinf=1.0, neginf=0.0)
            cand = np.clip(out * 255.0, 0, 255).astype(np.uint8)
            if (cand > 127).sum() >= (alpha > 127).sum() * 0.5:
                alpha = cand
            else:
                print("[!] guidedFilter 结果异常（%d px），跳过边缘精修" % int((cand > 127).sum()))
        except Exception as exc:
            print("[!] 边缘精修失败（%s），改用形态学平滑" % exc)
            alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    if feather > 0:
        alpha = cv2.GaussianBlur(alpha, (0, 0), feather)
    return alpha


def cmd_extract(args):
    """抠像：泛洪填充 → 显著性 → rect GrabCut 三级兜底，再做 GrabCut 精修与边缘精修。"""
    if cv2 is None:
        die("需要 opencv")
    img = load_rgba(args.input)
    rgb = img[:, :, :3]
    h, w = rgb.shape[:2]
    total = h * w

    def plausible(m):
        return m is not None and 0.02 * total < m.sum() < 0.88 * total

    method = "flood"
    m = flood_bg(rgb, args.tol)
    if not plausible(m):
        print("[i] 泛洪结果 %.1f%% 不合理，改用显著性检测" % (m.sum() * 100.0 / total))
        method = "saliency"
        m = saliency_fg(rgb)
    if not plausible(m):
        print("[i] 显著性结果仍不合理，改用 rect GrabCut")
        method = "rect"
        gm = np.zeros((h, w), np.uint8)
        mx, my = max(2, w // 20), max(2, h // 20)
        bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
        cv2.grabCut(rgb, gm, (mx, my, w - 2 * mx, h - 2 * my), bgd, fgd,
                    args.iters * 2, cv2.GC_INIT_WITH_RECT)
        m = largest_component(np.where((gm == cv2.GC_FGD) | (gm == cv2.GC_PR_FGD), 1, 0).astype(np.uint8))

    m = fill_holes(m) if args.fill_holes else m
    print("[i] 方法=%s  初始前景 %.1f%%" % (method, m.sum() * 100.0 / total))

    if args.grabcut:
        m2 = grabcut_refine(rgb, m, args.iters, args.erode, args.dilate)
        if plausible(m2):
            m = fill_holes(m2) if args.fill_holes else m2

    alpha = refine_alpha(rgb, m, args.radius if args.refine else 0, args.eps, args.feather)
    out = np.dstack([rgb, alpha])
    op = alpha > 127
    print("[i] 最终保留 %.1f%%  不透明像素 %d  包围盒 %s" % (
        float(op.mean()) * 100, int(op.sum()), cv2.boundingRect(m)))
    save_rgba(out, args.output)


# ----------------------------------------------------------------------
# 2) vectorize：彩色矢量化
# ----------------------------------------------------------------------
def strip_background(svg_path, key=(255, 0, 255), tol=42):
    """删掉所有「键控色」图层，得到透明底 SVG。

    为什么用键控色而不是白色：角色自身也有大量白色（头发/外套），
    按白色删会连人一起删；而 cutout 模式下背景层的排序也不固定，
    所以改成「铺一个画里不存在的品红底 -> 按颜色删所有该色层」，与顺序无关。
    """
    from lxml import etree

    tree = etree.parse(svg_path)
    root = tree.getroot()
    ns = root.nsmap.get(None)
    tag = lambda n: "{%s}%s" % (ns, n) if ns else n
    removed = 0
    for el in list(root):
        if el.tag != tag("path"):
            continue
        fill = (el.get("fill") or "").strip().lower()
        if not (fill.startswith("#") and len(fill) in (7, 9)):
            continue
        rgb = tuple(int(fill[i:i + 2], 16) for i in (1, 3, 5))
        if max(abs(rgb[i] - key[i]) for i in range(3)) <= tol:
            root.remove(el)
            removed += 1
    if removed:
        tree.write(svg_path, xml_declaration=True, encoding="utf-8")
    return removed


def cmd_vectorize(args):
    try:
        import vtracer
    except ImportError:
        die("需要 vtracer（pip install vtracer）")
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)

    # vtracer 不认透明通道：透明区先铺成键控色（默认品红），矢量化后再按颜色删掉该层
    img = Image.open(args.input).convert("RGBA")
    key = tuple(int(args.bg_key[i:i + 2], 16) for i in (1, 3, 5)) if args.bg_key.startswith("#") else (255, 0, 255)
    bg = Image.new("RGBA", img.size, key + (255,))
    flat = Image.alpha_composite(bg, img).convert("RGB")
    tmp = os.path.join(tempfile.gettempdir(), "dsh_vtracer_in.png")
    flat.save(tmp)

    mode = args.mode if args.mode in ("spline", "polygon", "none") else "spline"
    vtracer.convert_image_to_svg_py(
        tmp,
        args.output,
        colormode="color",
        hierarchical=args.hierarchical,
        mode=mode,
        filter_speckle=args.speckle,
        color_precision=args.precision,
        layer_difference=args.layer_diff,
        corner_threshold=60,
        length_threshold=4.0,
        max_iterations=10,
        splice_threshold=45,
        path_precision=args.path_precision,
    )
    stripped = 0 if args.keep_background else strip_background(args.output, key, args.bg_tol)
    size = os.path.getsize(args.output)
    with open(args.output, "r", encoding="utf-8", errors="ignore") as fh:
        body = fh.read()
    print("[ok] SVG %s  %.1f KB  path 数 %d  剥掉背景层 %d  颜色种类 %d" % (
        args.output, size / 1024, body.count("<path"), stripped,
        len(set(__import__("re").findall(r'fill="(#[0-9a-fA-F]{3,8})"', body)))))


# ----------------------------------------------------------------------
# 3) rasterize：SVG -> PNG（Edge headless）
# ----------------------------------------------------------------------
def cmd_rasterize(args):
    """SVG -> PNG。注意：Edge 的 --screenshot 路径必须是纯 ASCII，
    所以先写到临时目录再拷回目标（工作区路径含中文会让它静默失败）。"""
    import re
    import shutil
    edge = next((p for p in EDGE_CANDIDATES if os.path.exists(p) or p == "msedge"), None)
    if edge is None:
        die("找不到 msedge.exe")
    with open(args.input, "r", encoding="utf-8", errors="ignore") as fh:
        svg = fh.read()
    m = re.search(r'width="(\d+)"\s+height="(\d+)"', svg)
    ow, oh = (int(m.group(1)), int(m.group(2))) if m else (900, 1200)
    tw = args.width or ow
    th = int(round(oh * tw / max(1, ow)))
    # vtracer 常不写 viewBox：这时只改 width/height 内容不会缩放（只画到画布一角），
    # 所以缺 viewBox 必须先按原始尺寸补一个。
    head = re.search(r"<svg[^>]*>", svg)
    if head and "viewBox" not in head.group(0):
        svg = svg.replace(head.group(0),
                          head.group(0)[:-1] + ' viewBox="0 0 %d %d">' % (ow, oh), 1)
    svg2 = re.sub(r'(<svg[^>]*?)(width="\d+"\s+height="\d+")',
                  r'\1width="%d" height="%d"' % (tw, th), svg, count=1)
    w, h = tw, th
    tmpdir = tempfile.gettempdir()
    tmp_svg = os.path.join(tmpdir, "dsh_raster_in.svg")
    tmp_png = os.path.join(tmpdir, "dsh_raster_out.png")
    with open(tmp_svg, "w", encoding="utf-8") as fh:
        fh.write(svg2)
    if os.path.exists(tmp_png):
        os.remove(tmp_png)
    cmd = [edge, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
           "--force-device-scale-factor=1", "--virtual-time-budget=4000",
           "--default-background-color=00000000",
           "--user-data-dir=%s" % os.path.join(tmpdir, "dsh_edge_profile"),
           "--screenshot=%s" % tmp_png, "--window-size=%d,%d" % (w, h),
           "file:///" + tmp_svg.replace("\\", "/")]
    r = subprocess.run(cmd, capture_output=True, timeout=180)
    if not os.path.exists(tmp_png) or os.path.getsize(tmp_png) < 200:
        tail = (r.stderr or b"").decode("utf-8", "ignore")[-400:]
        die("光栅化失败（stderr: %s）" % tail.replace("\n", " "))
    out = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    shutil.copyfile(tmp_png, out)
    print("[ok] 光栅化 %s (%dx%d, %.1f KB)" % (out, w, h, os.path.getsize(out) / 1024))


# ----------------------------------------------------------------------
# 4) compare：客观比对
# ----------------------------------------------------------------------
def cmd_compare(args):
    """客观比对：先统一到同一底色再算 SSIM/PSNR（否则透明区会污染指标），
    另外单独给出不透明区 IoU 与感知哈希距离。"""
    from skimage.metrics import structural_similarity as ssim
    from skimage.metrics import peak_signal_noise_ratio as psnr
    a = Image.open(args.a).convert("RGBA")
    b = Image.open(args.b).convert("RGBA")
    if a.size != b.size:
        print("[i] 尺寸不同 %s -> 缩放第二张" % (a.size,))
        b = b.resize(a.size, Image.LANCZOS)

    # 先各自记录 alpha（用于 IoU），再合成到白底上比较
    al_a = np.asarray(a)[:, :, 3] > 127
    al_b = np.asarray(b)[:, :, 3] > 127
    bg = Image.new("RGBA", a.size, (255, 255, 255, 255))
    ca = Image.alpha_composite(bg, a)
    cb = Image.alpha_composite(bg, b)
    ga = np.asarray(ca.convert("L")).astype(np.float64)
    gb = np.asarray(cb.convert("L")).astype(np.float64)
    ca_rgb = np.asarray(ca.convert("RGB")).astype(np.float64)
    cb_rgb = np.asarray(cb.convert("RGB")).astype(np.float64)

    s = ssim(ga, gb, data_range=255)
    p = psnr(ga, gb, data_range=255)
    mad = float(np.abs(ca_rgb - cb_rgb).mean())
    inter = float((al_a & al_b).sum())
    union = float((al_a | al_b).sum()) or 1.0

    print("SSIM  %.4f   (1.0 = 完全一致；>0.90 视觉几乎无差别)" % s)
    print("PSNR  %.2f dB" % p)
    print("合成白底后 RGB 平均绝对误差 %.2f" % mad)
    print("不透明区 IoU %.4f  (甲 %.1f%% / 乙 %.1f%%)" % (inter / union, al_a.mean() * 100, al_b.mean() * 100))
    try:
        import imagehash
        print("感知哈希距离 %d" % (imagehash.phash(ca) - imagehash.phash(cb)))
    except ImportError:
        pass
    ok = s > args.threshold
    print("[%s] 判定阈值 SSIM>%.2f" % ("PASS" if ok else "FAIL", args.threshold))
    return 0 if ok else 1


# ----------------------------------------------------------------------
# 5) upscale：高质量放大
# ----------------------------------------------------------------------
def cmd_upscale(args):
    img = Image.open(args.input).convert("RGBA")
    w, h = img.width * args.factor, img.height * args.factor
    up = img.resize((w, h), Image.LANCZOS)
    if args.sharpen > 0:
        rgb = up.convert("RGB").filter(
            ImageFilter.UnsharpMask(radius=2, percent=int(args.sharpen * 100), threshold=2))
        up = Image.merge("RGBA", (*rgb.split(), up.split()[3]))
    up.save(args.output)
    print("[ok] %s  %dx%d -> %dx%d" % (args.output, img.width, img.height, w, h))


# ----------------------------------------------------------------------
# 6) transplant：无缝移植（Poisson 融合）
# ----------------------------------------------------------------------
def cmd_transplant(args):
    if cv2 is None:
        die("需要 opencv")
    base = load_rgba(args.base)
    patch = load_rgba(args.patch)
    x, y, w, h = [int(v) for v in args.box.split(",")]
    patch = np.asarray(Image.fromarray(patch).resize((w, h), Image.LANCZOS))
    center = (x + w // 2, y + h // 2)
    if patch.shape[2] == 4:
        mask = (patch[:, :, 3] > 20).astype(np.uint8) * 255
        if mask.sum() == 0:
            mask = np.full(patch.shape[:2], 255, np.uint8)
    else:
        mask = np.full(patch.shape[:2], 255, np.uint8)
    out = cv2.seamlessClone(patch[:, :, :3], base[:, :, :3].copy(), mask, center, cv2.NORMAL_CLONE)
    alpha = base[:, :, 3].copy()
    res = np.dstack([out, alpha])
    save_rgba(res, args.output)


# ----------------------------------------------------------------------
# 7) inpaint：修补
# ----------------------------------------------------------------------
def cmd_inpaint(args):
    if cv2 is None:
        die("需要 opencv")
    img = load_rgba(args.input)
    mask = np.asarray(Image.open(args.mask).convert("L"))
    if mask.shape[:2] != img.shape[:2]:
        die("蒙版尺寸需与输入一致")
    bgr = cv2.cvtColor(img[:, :, :3], cv2.COLOR_RGB2BGR)
    fixed = cv2.inpaint(bgr, (mask > 127).astype(np.uint8), args.radius, cv2.INPAINT_TELEA)
    out = np.dstack([cv2.cvtColor(fixed, cv2.COLOR_BGR2RGB), img[:, :, 3]])
    save_rgba(out, args.output)


def build_parser():
    p = argparse.ArgumentParser(description="流萤桌宠建模工具链")
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("extract", help="抠像（边框建模 + GrabCut + 精修）")
    e.add_argument("input"); e.add_argument("output")
    e.add_argument("--tol", type=float, default=26.0, help="泛洪容差（简单背景用）")
    e.add_argument("--grabcut", type=int, default=1, help="1=再做一轮 GrabCut 精修")
    e.add_argument("--iter", dest="iters", type=int, default=5, help="GrabCut 迭代次数")
    e.add_argument("--erode", type=int, default=2, help="确定前景的腐蚀次数")
    e.add_argument("--dilate", type=int, default=2, help="确定背景的膨胀次数")
    e.add_argument("--refine", type=int, default=1, help="1=导向滤波精修边缘")
    e.add_argument("--radius", type=int, default=4)
    e.add_argument("--eps", type=float, default=1e-4)
    e.add_argument("--feather", type=float, default=0.8)
    e.add_argument("--fill-holes", type=int, default=1)
    e.set_defaults(func=cmd_extract)

    v = sub.add_parser("vectorize", help="彩色矢量化")
    v.add_argument("input"); v.add_argument("output")
    v.add_argument("--mode", default="spline", choices=["spline", "polygon", "none"])
    v.add_argument("--colors", type=int, default=16, help="（参考值，实际由 precision/layer-diff 控制）")
    v.add_argument("--precision", type=int, default=5, help="颜色精度 4~6：越低颜色越少、文件越小")
    v.add_argument("--layer-diff", type=int, default=32, help="层间色差阈值：越大越简化")
    v.add_argument("--speckle", type=int, default=8, help="滤除小于该像素数的碎块")
    v.add_argument("--path-precision", type=int, default=6)
    v.add_argument("--hierarchical", default="cutout", choices=["stacked", "cutout"],
                   help="cutout 各层互不重叠（背景可整层剥离）；stacked 为传统堆叠")
    v.add_argument("--keep-background", type=int, default=0, help="1=保留背景层（不透明）")
    v.add_argument("--bg-tol", type=int, default=42, help="键控色容差")
    v.add_argument("--bg-key", default="#ff00ff", help="键控底色（画里不应出现的颜色）")
    v.set_defaults(func=cmd_vectorize)

    r = sub.add_parser("rasterize", help="SVG -> PNG")
    r.add_argument("input"); r.add_argument("output")
    r.add_argument("--width", type=int, default=0)
    r.set_defaults(func=cmd_rasterize)

    c = sub.add_parser("compare", help="SSIM/PSNR/IoU 比对")
    c.add_argument("a"); c.add_argument("b")
    c.add_argument("--threshold", type=float, default=0.9)
    c.set_defaults(func=cmd_compare)

    u = sub.add_parser("upscale", help="高质量放大")
    u.add_argument("input"); u.add_argument("output")
    u.add_argument("--factor", type=int, default=2)
    u.add_argument("--sharpen", type=float, default=0.6)
    u.set_defaults(func=cmd_upscale)

    t = sub.add_parser("transplant", help="无缝移植（Poisson）")
    t.add_argument("base"); t.add_argument("patch"); t.add_argument("output")
    t.add_argument("--box", required=True, help="x,y,w,h")
    t.set_defaults(func=cmd_transplant)

    i = sub.add_parser("inpaint", help="修补缺口")
    i.add_argument("input"); i.add_argument("mask"); i.add_argument("output")
    i.add_argument("--radius", type=int, default=3)
    i.set_defaults(func=cmd_inpaint)
    return p


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    sys.exit(args.func(args) or 0)
