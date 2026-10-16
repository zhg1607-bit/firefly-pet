# -*- coding: utf-8 -*-
"""make_memes.py v5
从 character/reference.png 抠出「表情参考」4 个头像做表情包。

v4 的错误：把左下角「细节展示」第二行的 4 个方块（裙摆花纹/袖口花饰/腿部纹样/鞋子）当成了表情。
v5 修正：表情参考是右下角的 2x2 网格（x939..1274, y538..829），每张都有较多皮肤像素与眼睛色像素。

布局（原图坐标）：
    smile      x944..1098 y541..667      wink      x1110..1265 y538..683
    surprised  x939..1094 y689..827      shy       x1108..1274 y690..829
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "character" / "reference.png"
OUT = ROOT / "memes"
WORK = ROOT / "work"
OUT.mkdir(exist_ok=True)
WORK.mkdir(exist_ok=True)

# (键, x0, x1, y0, y1) —— 已各外扩 4px
REGIONS = [
    ("smile",     940, 1102, 537, 671),
    ("wink",     1106, 1269, 534, 687),
    ("surprised", 935, 1098, 685, 831),
    ("shy",      1104, 1278, 686, 833),
]

ALPHA_TH = 16


def alpha_box(a, pad=2):
    ys, xs = np.where(a[:, :, 3] > ALPHA_TH)
    y0, y1 = max(0, ys.min() - pad), ys.max() + 1 + pad
    x0, x1 = max(0, xs.min() - pad), xs.max() + 1 + pad
    return y0, y1, x0, x1


def corner_color(tile):
    """4 个角各取 3x3 均值，返回 (颜色列表, 是否都不透明)"""
    h, w = tile.shape[:2]
    pts = [(1, 1), (1, w - 4), (h - 4, 1), (h - 4, w - 4)]
    cols = [tile[y:y + 3, x:x + 3, :3].reshape(-1, 3).mean(axis=0) for y, x in pts]
    a = [tile[y:y + 3, x:x + 3, 3].mean() for y, x in pts]
    return np.array(cols), min(a) > 250


def clear_card(tile, thresh=14.0):
    """从四角 floodfill 去掉卡片底（颜色相近且相互连通），返回新 tile 与被清除比例。"""
    from PIL import ImageDraw as _D
    h, w = tile.shape[:2]
    im = Image.fromarray(tile, "RGBA")
    for pt in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        ImageDraw.floodfill(im, pt, (0, 0, 0, 0), thresh=thresh)
    out = np.asarray(im).astype(np.uint8)
    before = (tile[:, :, 3] > 128).sum()
    after = (out[:, :, 3] > 128).sum()
    return out, 1.0 - after / max(1, before)


def main():
    ref = np.asarray(Image.open(SRC).convert("RGBA"))
    made = {}
    for key, x0, x1, y0, y1 in REGIONS:
        tile = ref[y0:y1, x0:x1].copy()
        by0, by1, bx0, bx1 = alpha_box(tile, 2)
        tile = tile[by0:by1, bx0:bx1]
        cols, all_opaque = corner_color(tile)
        spread = float(np.abs(cols - cols.mean(axis=0)).max())
        note = "保留 alpha 原样"
        if all_opaque and spread < 18:
            tile2, cleared = clear_card(tile, thresh=14.0)
            if cleared < 0.30:  # 合理性检查：别把角色本身吃掉
                tile = tile2
                note = f"去除卡片底（清除 {cleared:.1%} 不透明像素，底色 RGB{cols.mean(axis=0).astype(int).tolist()}）"
            else:
                note = f"卡片检测到但清除比例过大({cleared:.1%})，改为保留原样"
        Image.fromarray(tile, "RGBA").save(OUT / f"{key}.png")
        made[key] = tile
        op = (tile[:, :, 3] > 128).mean()
        print(f"{key:10} {tile.shape[1]}x{tile.shape[0]}  不透明 {op:.0%}  角部均值 {cols.mean(axis=0).astype(int).tolist()}  -> {note}")

    # 配置片段（插件 main-config.jsonc 的 memes 字段）
    cfg = {
        "smile": "开心微笑的表情头像",
        "wink": "俏皮眨单眼的头像",
        "surprised": "惊讶瞪大眼睛的头像",
        "shy": "害羞低头脸红的头像",
    }
    lines = ['"memes": {']
    for i, (k, v) in enumerate(cfg.items()):
        lines.append(f'    "{k}": "{v}"' + ("," if i < len(cfg) - 1 else ""))
    lines.append("  }")
    (ROOT / "report" / "memes_config.jsonc").write_text("\n".join(lines), encoding="utf-8")
    print("配置片段 -> report/memes_config.jsonc")

    # 来源 / 结果 对照图
    def checker(w, h, tile=14, c1=(220, 220, 220), c2=(196, 196, 196)):
        g = (np.indices((h, w)).sum(axis=0) // tile) % 2
        img = np.empty((h, w, 3), np.uint8)
        img[g == 0] = c1
        img[g == 1] = c2
        return img

    TW, TH, PAD = 300, 240, 10
    rows = []
    for key, x0, x1, y0, y1 in REGIONS:
        row = Image.new("RGB", (2 * (TW + PAD) + PAD, TH + 26), (255, 255, 255))
        for idx, (img_a, label) in enumerate([
            (ref[y0:y1, x0:x1], f"{key}  source(参考图区域)"),
            (made[key], f"{key}  extracted(生成的表情包)"),
        ]):
            src = Image.fromarray(img_a.astype(np.uint8), "RGBA")
            src.thumbnail((TW, TH - 4), Image.LANCZOS)
            cell = Image.new("RGBA", (TW, TH), (0, 0, 0, 0))
            cell.paste(Image.fromarray(checker(TW, TH), "RGB"))
            cell.paste(src, ((TW - src.width) // 2, (TH - src.height) // 2), src)
            row.paste(cell.convert("RGB"), (PAD + idx * (TW + PAD), 0))
            ImageDraw.Draw(row).text((PAD + idx * (TW + PAD), TH + 6), label, fill=(40, 40, 40))
        rows.append(row)
    sheet = Image.new("RGB", (rows[0].width, sum(r.height for r in rows)), (255, 255, 255))
    yy = 0
    for r in rows:
        sheet.paste(r, (0, yy))
        yy += r.height
    sheet.save(WORK / "meme_check_sheet.png")
    print("对照图 -> work/meme_check_sheet.png")


if __name__ == "__main__":
    main()
