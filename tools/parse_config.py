# -*- coding: utf-8 -*-
"""解析上游插件的 assets/config.jsonc（JSONC：含 // 行尾注释、块注释、尾逗号）。

用法: python parse_config.py <config.jsonc> [输出.json]
"""
import json
import re
import sys


def strip_jsonc(text: str) -> str:
    out = []
    i, n = 0, len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\":
                if i + 1 < n:
                    out.append(text[i + 1])
                    i += 2
                    continue
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] not in "\r\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        out.append(c)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def main() -> int:
    src = sys.argv[1]
    with open(src, encoding="utf-8") as fh:
        cfg = json.loads(strip_jsonc(fh.read()))
    if len(sys.argv) > 2:
        with open(sys.argv[2], "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)
    a = cfg.get("animations", {})
    print("animations 键:", list(a.keys()))
    for k, v in a.items():
        print(f"  {k}: {len(v) if not isinstance(v, dict) else len(v)}")
    total = set()
    for k in ("idle", "turn", "drag", "clicks", "moves"):
        total |= set(a.get(k, []))
    for c in a.get("categories", []):
        total |= set(c.get("actions", []))
    # events 嵌在 animations.events 下：{事件名: [档位...]}，档位是字符串或候选数组
    ev_names = set()
    for _k, slots in a.get("events", {}).items():
        slots = slots if isinstance(slots, list) else [slots]
        for it in slots:
            if isinstance(it, str):
                ev_names.add(it)
            elif isinstance(it, list):
                ev_names |= {x for x in it if isinstance(x, str)}
    print("普通动画名合计:", len(total))
    print("事件动画名合计:", len(ev_names))
    print("全部合计:", len(total | ev_names))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
