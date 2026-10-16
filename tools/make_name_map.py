# -*- coding: utf-8 -*-
"""生成「定制版动作名 → 建议文件名」对照表。

背景：dsh-pet 插件播放的动画名来自配置池（`assets/config.jsonc` 的
animations.idle/turn/drag/clicks/moves/categories/events），实际文件从
`$DSH_HOME/dsh-pet/main-animation/webm/<名>.webm` 取，**用户目录优先于包内素材**。
所以只要把我们生成的 webm 命名成「插件内置的动画名」，刷新页面即可无缝替换成定制形象，
一行配置都不用改；只有改了标题的少数动作需要额外往配置池里加名字。

用法: python tools/make_name_map.py
产物:
  prompts/动作名对照表.md
  report/action_names.csv
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import parse_config  # noqa: E402  同目录模块

ROOT = Path(__file__).resolve().parent.parent
WS = ROOT.parent
UPSTREAM_PROMPTS = WS / "dsh-pet-assets" / "prompts" / "action-10s.md"
CUSTOM_PROMPTS = ROOT / "prompts" / "action-10s.md"
UPSTREAM_CONFIG = ROOT / "work" / "upstream-config.jsonc"

# 上游提示词里另有 6 张通知图标与内置事件动画名，这里只做动作对照


# 定制版文件里 `## ` 小节 = 角色设定卡 1 + 通用前缀 1 + 动作 106，前两个不是动作
NON_ACTION = {"通用前缀", "角色设定卡（固定引用，每次生成都必须与参考图完全一致）"}


def titles(path: Path, drop_non_action: bool = False) -> list[str]:
    out = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        if line.startswith("## "):
            t = line[3:].strip()
            if drop_non_action and t in NON_ACTION:
                continue
            out.append(t)
    return out if drop_non_action else out[1:]


def builtin_names(cfg: dict) -> tuple[set[str], set[str], dict[str, list[str]]]:
    a = cfg["animations"]
    normal: set[str] = set()
    pools: dict[str, list[str]] = {}
    for k in ("idle", "turn", "drag", "clicks", "moves"):
        pools[k] = list(a.get(k, []))
        normal |= set(pools[k])
    for c in a.get("categories", []):
        pools[f"分类-{c.get('id')}"] = list(c.get("actions", []))
        normal |= set(pools[f"分类-{c.get('id')}"])
    ev: set[str] = set()
    for k, slots in a.get("events", {}).items():
        for it in (slots if isinstance(slots, list) else [slots]):
            if isinstance(it, str):
                ev.add(it)
                pools.setdefault(f"事件-{k}", []).append(it)
            elif isinstance(it, list):
                for x in it:
                    if isinstance(x, str):
                        ev.add(x)
                        pools.setdefault(f"事件-{k}", []).append(x)
    return normal, ev, pools


def main() -> int:
    old = titles(UPSTREAM_PROMPTS)
    new = titles(CUSTOM_PROMPTS, drop_non_action=True)
    cfg = json.loads(parse_config.strip_jsonc(UPSTREAM_CONFIG.read_text(encoding="utf-8")))
    normal, ev, pools = builtin_names(cfg)
    builtin = normal | ev
    assert len(old) == len(new), f"动作数不一致: 上游 {len(old)} / 定制 {len(new)}"

    rows = []
    for i, (o, n) in enumerate(zip(old, new), 1):
        hit = o in builtin
        kind = "事件" if o in ev else ("常规" if o in normal else "—")
        renamed = "是" if o != n else ""
        rows.append({
            "序号": i,
            "原版动作名": o,
            "定制版动作名": n,
            "标题有改动": renamed,
            "是否插件内置名": "是" if hit else "否",
            "内置归属": kind if hit else "",
            "建议文件名": f"{o}.webm",
            "说明": "直接覆盖内置动画（零配置）" if hit else "需在配置池里加名字",
        })

    hit_n = sum(1 for r in rows if r["是否插件内置名"] == "是")
    ren_n = sum(1 for r in rows if r["标题有改动"] == "是")

    # —— CSV ——
    csv_path = ROOT / "report" / "action_names.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # —— Markdown ——
    lines = [
        "# 动作名对照表（定制版 ↔ 插件内置动画名）",
        "",
        "> 本表由 `tools/make_name_map.py` 自动生成，请勿手改。",
        "",
        "## 怎么用（三步）",
        "",
        "1. 把某个动作生成的 10 秒绿幕视频放进 `video/<建议文件名>`（`<建议文件名>` 见下表「建议文件名」列）。",
        "2. 跑完素材链后，把 `step04\\<同名>.webm` 复制到 `%DSH_HOME%\\dsh-pet\\main-animation\\webm\\`。",
        "3. 刷新 DSH 页面。文件名 = 插件内置动画名时，**用户目录素材优先于包内素材**，无需改任何配置。",
        "",
        "下表里「是否插件内置名 = 否」的动作（标题被我改写过，插件不认识新名字），"
        "需要把它们加进 `%DSH_HOME%\\dsh-pet\\main-config.jsonc` 的 `animations` 池才会被播放；"
        "也可以直接沿用「建议文件名」列（= 原版动作名）落盘，这样依旧是零配置覆盖。",
        "",
        f"- 动作总数：**{len(rows)}**",
        f"- 标题被改写的动作：**{ren_n}** 个（见「标题有改动」列）",
        f"- 文件名能命中插件内置动画名的：**{hit_n}** 个（零配置覆盖）",
        f"- 插件内置动画名总数：**{len(builtin)}**（常规 {len(normal)} + 事件 {len(ev)}）",
        "",
        "## 对照表",
        "",
        "| # | 原版动作名（= 建议文件名） | 定制版动作名 | 内置名 | 说明 |",
        "|---:|---|---|:---:|---|",
    ]
    for r in rows:
        mark = "✅" if r["是否插件内置名"] == "是" else "➕"
        nn = r["定制版动作名"]
        nn = f"**{nn}**" if r["标题有改动"] == "是" else nn
        lines.append(f"| {r['序号']} | `{r['原版动作名']}` | {nn} | {mark} | {r['说明']} |")
    lines += ["", "## 插件内置动画池（供参考）", ""]
    for k, v in pools.items():
        lines.append(f"- **{k}**（{len(v)}）：{'、'.join(v)}")
    md = ROOT / "prompts" / "动作名对照表.md"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"对照表: {md}")
    print(f"CSV:    {csv_path}")
    print(f"动作 {len(rows)} 个；标题改写 {ren_n} 个；命中内置名 {hit_n} 个；内置名总数 {len(builtin)}")
    miss = [r for r in rows if r["是否插件内置名"] == "否"]
    if miss:
        print("未命中内置名的动作：" + "、".join(r["原版动作名"] for r in miss))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
