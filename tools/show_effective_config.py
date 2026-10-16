#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""读取 dsh-pet 宿主的生效配置（GET /dsh-pet-7340/config），打印关键字段。

用法: python tools/show_effective_config.py [base_url]
"""
from __future__ import annotations

import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:19387/dsh-pet-7340"


def main() -> int:
    with urllib.request.urlopen(BASE + "/config", timeout=20) as r:
        raw = json.load(r)
    # /config 返回的是「条目 → 该条目完成品配置」的映射（条目 key 即素材根，主配置=main），
    # 也兼容拍平后的形状（顶层直接有 pets）。
    if isinstance(raw, dict) and "pets" not in raw:
        entries = raw
    else:
        entries = {"main": raw}
    print("条目 key:", list(entries))

    for key, cfg in entries.items():
        if not isinstance(cfg, dict):
            print(f"\n[{key}] 非对象: {cfg!r}")
            continue
        print(f"\n===== 条目 [{key}] =====")
        print("字段:", list(cfg))
        for p in cfg.get("pets") or []:
            print("  pet:", json.dumps(p, ensure_ascii=False))

        wp = cfg.get("whisperPrompt")
        if isinstance(wp, str):
            print(f"  whisperPrompt ({len(wp)} 字): {wp}")
        else:
            print(f"  whisperPrompt: {wp!r}")

        memes = cfg.get("memes") or {}
        print(f"  memes: {len(memes)} 条 -> {list(memes)}")

        for k in ("animationWeights", "eventsRefreshSec", "chatImageLimit", "chatMemoryRounds",
                  "notificationsEnabled", "whisperImageEnabled", "chatImageEnabled", "confineToScreen"):
            print(f"  {k}: {json.dumps(cfg.get(k), ensure_ascii=False)}")

        anims = cfg.get("animations") or {}
        print("  animations 池:", {k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in anims.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
