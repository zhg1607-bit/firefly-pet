#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""盘点已安装 dsh-pet 插件的内置配置与素材池（部署前事实核对）。

用法:
    python tools/inspect_plugin_config.py [包根]

默认包根 = C:\\Users\\PC-7020\\.dsh\\profiles\\desktop\\node_modules\\dsh-pet
输出:
    - 默认 assets/config.jsonc 的顶层键结构
    - animations 各池（键 → 名字列表）+ 与 assets/webm 实际文件比对
    - memes 映射（键 → 描述）
    - 用户层 main-config.jsonc 覆盖了哪些顶层键
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

DEFAULT_PKG = Path(r"C:\Users\PC-7020\.dsh\profiles\desktop\node_modules\dsh-pet")
USER_ROOT = Path(r"C:\Users\PC-7020\.dsh\dsh-pet")


def strip_jsonc(text: str) -> str:
    """剥 // 与 /* */ 注释、去尾逗号（字符串内不误伤）。"""
    out = []
    i, n = 0, len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        out.append(c)
        i += 1
    s = "".join(out)
    s = re.sub(r",(\s*[}\]])", r"\1", s)
    return s


def load_jsonc(p: Path):
    return json.loads(strip_jsonc(p.read_text(encoding="utf-8")))


def main() -> int:
    pkg = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PKG
    default_file = pkg / "assets" / "config.jsonc"
    user_file = USER_ROOT / "main-config.jsonc"

    print(f"包根: {pkg}")
    print(f"默认配置: {default_file}  ({default_file.stat().st_size} B)")
    default = load_jsonc(default_file)
    print("\n=== 默认配置顶层键 ===")
    for k, v in default.items():
        t = type(v).__name__
        extra = ""
        if isinstance(v, dict):
            extra = f" keys={list(v)[:12]}"
        elif isinstance(v, list):
            extra = f" len={len(v)}"
        print(f"  {k}: {t}{extra}")

    print("\n=== animations 池（递归展开）===")
    anims = default.get("animations") or {}
    webm_dir = pkg / "assets" / "webm"
    have = {p.stem for p in webm_dir.glob("*.webm")} if webm_dir.is_dir() else set()
    leaf: list[tuple[str, str]] = []  # (池路径, 名字)

    def walk(node, path: str) -> None:
        if isinstance(node, str):
            leaf.append((path, node))
            return
        if isinstance(node, list):
            for i, x in enumerate(node):
                walk(x, f"{path}[{i}]")
            return
        if isinstance(node, dict):
            # 形如 {名称: 权重} 的权重表（值全是数字）→ 键即名字
            if node and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in node.values()):
                for k in node:
                    leaf.append((path, k))
                return
            for k, v in node.items():
                walk(v, f"{path}.{k}")

    walk(anims, "animations")
    grouped: dict[str, list[str]] = {}
    for p, n in leaf:
        grouped.setdefault(p, []).append(n)
    for p, names in grouped.items():
        miss = [nm for nm in names if nm not in have]
        print(f"  {p}: {len(names)} 个" + (f"  [缺文件 {len(miss)}: {miss}]" if miss else "  (文件齐全)"))
        if len(names) <= 8:
            print(f"      {names}")
    all_names = [n for _, n in leaf]
    print(f"  —— 池内名字合计 {len(all_names)}，去重 {len(set(all_names))}；assets/webm 实际 {len(have)} 个文件")
    orphan = sorted(have - set(all_names))
    print(f"  未被任何池引用的文件 {len(orphan)}: {orphan}")
    extra = sorted(set(all_names) - have)
    print(f"  池内引用但无文件的 {len(extra)}: {extra}")

    print("\n=== workStatusTexts ===")
    for i, t in enumerate(default.get("workStatusTexts") or []):
        print(f"  [{i}] {t!r}")

    print("\n=== memes 映射（键 → 描述）===")
    memes = default.get("memes") or {}
    meme_files = {p.stem for p in (pkg / "assets" / "memes").glob("*.png")}
    if isinstance(memes, dict):
        print(f"  条目 {len(memes)} 个；assets/memes 实际 {len(meme_files)} 张图")
        for k, v in memes.items():
            flag = "" if k in meme_files else "  <== 缺图"
            print(f"    {k!r}: {v!r}{flag}")
        missing_img = sorted(meme_files - set(memes))
        if missing_img:
            print(f"  有图但未登记: {missing_img}")
    else:
        print(f"  memes 类型异常: {type(memes).__name__} = {memes!r}")

    print("\n=== 其他关键字段 ===")
    for k in ("whisperPrompt", "chatPrompt", "eventsRefreshSec", "physics", "pets"):
        if k in default:
            v = default[k]
            if isinstance(v, list):
                print(f"  {k}: list len={len(v)} -> {json.dumps(v, ensure_ascii=False)[:400]}")
            elif isinstance(v, dict):
                print(f"  {k}: dict keys={list(v)}")
            else:
                print(f"  {k}: {str(v)[:200]}")

    print("\n=== 用户层覆盖 ===")
    if user_file.exists():
        user = load_jsonc(user_file)
        print(f"  {user_file} ({user_file.stat().st_size} B) 顶层键: {list(user)}")
        print(f"  覆盖默认的键: {sorted(set(user) & set(default))}")
        print(f"  用户新增的键: {sorted(set(user) - set(default))}")
    else:
        print(f"  （不存在）{user_file}")

    print("\n=== 用户数据目录现状 ===")
    for sub in ("main-animation/webm", "main-animation/mov", "memes", "pet"):
        d = USER_ROOT / sub
        if d.is_dir():
            files = sorted(p.name for p in d.iterdir())
            print(f"  {sub}/: {len(files)} 项 {files[:8]}")
        else:
            print(f"  {sub}/: （不存在）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
