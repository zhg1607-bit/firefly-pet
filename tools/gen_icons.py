# -*- coding: utf-8 -*-
"""gen_icons.py —— 用头部抠图生成 6 张通知图标（扁平贴纸风）：
512x512 / 透明背景 / 角色头部 + 白色描边贴纸圈 + 右上角彩色圆形符号徽章 / 无文字。
输出 work\icons\notify-{done,error,truncated,approval,question,test}.png + work\icons_sheet.png。"""
import sys
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import binary_dilation

sys.stdout.reconfigure(encoding="utf-8")

ROOT = r"D:\wd\deepseek-harness\default-workspace\dsh-pet-custom"
WORK = ROOT + r"\work"

head = np.asarray(Image.open(ROOT + r"\character\head.png").convert("RGBA")).astype(np.float32)
hrgb, ha = head[:, :, :3], head[:, :, 3]
ha[ha >= 200] = 255.0
head_im = Image.fromarray(np.dstack([hrgb, ha]).astype(np.uint8), "RGBA")

ICONS = {
    "done":      ("#5FC9AE", "check"),
    "error":     ("#F28080", "cross"),
    "truncated": ("#BFBFBF", "dots"),
    "approval":  ("#F2C14E", "bang"),
    "question":  ("#79B4E8", "question"),
    "test":      ("#F0A05A", "wrench"),
}

def checker(w, h, tile=16, c1=(220, 220, 220), c2=(196, 196, 196)):
    g = (np.indices((h, w)).sum(axis=0) // tile) % 2
    img = np.empty((h, w, 3), np.uint8)
    img[g == 0] = c1
    img[g == 1] = c2
    return img

def draw_symbol(d, kind, cx, cy):
    """在徽章圆心 (cx,cy) 上画白色扁平符号（r=56 徽章）。"""
    white = (255, 255, 255)
    if kind == "check":
        d.line([(cx - 26, cy + 6), (cx + 2, cy + 34), (cx + 32, cy - 28)], fill=white, width=16, joint="curve")
    elif kind == "cross":
        d.line([(cx - 26, cy - 30), (cx + 26, cy + 30)], fill=white, width=16)
        d.line([(cx + 26, cy - 30), (cx - 26, cy + 30)], fill=white, width=16)
    elif kind == "dots":
        for dx in (-26, 0, 26):
            d.ellipse([cx + dx - 13, cy - 13, cx + dx + 13, cy + 13], fill=white)
    elif kind == "bang":
        d.rounded_rectangle([cx - 8, cy - 38, cx + 8, cy + 10], radius=8, fill=white)
        d.ellipse([cx - 11, cy + 30, cx + 11, cy + 52], fill=white)
    elif kind == "question":
        d.arc([cx - 30, cy - 46, cx + 30, cy + 14], start=180, end=90, fill=white, width=16)
        d.ellipse([cx - 11, cy + 38, cx + 11, cy + 60], fill=white)
    elif kind == "wrench":
        d.arc([cx - 22, cy - 42, cx + 38, cy + 18], start=90, end=270, fill=white, width=16)
        d.line([(cx + 6, cy + 12), (cx - 22, cy + 40)], fill=white, width=16)

def make_icon(key, color):
    c = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    d = ImageDraw.Draw(c)
    # 头部：宽度 82%（420px），底部贴边，留 12px 边距
    scale = 420 / head_im.width
    hh = int(head_im.height * scale)
    h = head_im.resize((420, hh), Image.LANCZOS)
    hx, hy = (512 - 420) // 2, 512 - hh - 12
    # 白色贴纸描边（把头部 alpha 放大 6px 的轮廓涂白，再贴头部本体）
    mask = np.asarray(h)[:, :, 3] > 128
    ring = binary_dilation(mask, iterations=8) & ~binary_dilation(mask, iterations=3)
    for yy, xx in np.argwhere(ring):
        c.putpixel((hx + xx, hy + yy), (255, 255, 255, 255))
    c.paste(h, (hx, hy), h)
    # 右上角徽章
    cx, cy, r = 430, 86, 56
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 255, 255), width=6)
    draw_symbol(d, ICONS[key][1], cx, cy)
    c.save(f"{WORK}\\icons\\notify-{key}.png")
    return c

import os
os.makedirs(f"{WORK}\\icons", exist_ok=True)
made = {k: make_icon(k, v[0]) for k, v in ICONS.items()}
print("icons written:", len(made))

# ---- 对照图 3x2 ----
CELL, PAD = 300, 12
sheet = Image.new("RGB", (3 * (CELL + PAD) + PAD, 2 * (CELL + 30 + PAD) + PAD), (255, 255, 255))
d = ImageDraw.Draw(sheet)
for i, (key, ic) in enumerate(made.items()):
    r, c = divmod(i, 3)
    x, y = PAD + c * (CELL + PAD), PAD + r * (CELL + 30 + PAD)
    cell = Image.new("RGBA", (CELL, CELL), (0, 0, 0, 0))
    cell.paste(Image.fromarray(checker(CELL, CELL)), (0, 0))
    ic2 = ic.resize((CELL, CELL), Image.LANCZOS)
    cell.paste(ic2, (0, 0), ic2)
    sheet.paste(cell.convert("RGB"), (x, y))
    d.text((x + 2, y + CELL + 6), f"notify-{key}.png", fill=(40, 40, 40))
sheet.save(WORK + r"\icons_sheet.png")
print("sheet:", WORK + r"\icons_sheet.png")
