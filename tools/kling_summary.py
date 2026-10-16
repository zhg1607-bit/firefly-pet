# -*- coding: utf-8 -*-
"""从 kling who_am_i 的 JSON 里提炼能力清单（模型 / 关键参数 / 输入）。"""
import json
import sys
from pathlib import Path

p = Path(sys.argv[1])
d = json.loads(p.read_text(encoding="utf-8-sig"))
body = d.get("body", d)
print("userId:", body.get("user", {}).get("userId"), " mcpVersion:", body.get("mcpVersion"))
av = body.get("availableModels", {})
print("tools:", ", ".join(av.keys()))
for tool, spec in av.items():
    print("\n=== %s  (default=%s)" % (tool, spec.get("defaultModel")))
    for m in spec.get("models", []):
        al = m.get("alias", "")
        args = m.get("arguments", []) or []
        keys = []
        for a in args:
            if a.get("name") in ("duration", "resolution", "aspectRatio", "mode", "model", "cfgScale",
                                 "negativePrompt", "count", "motionDirection", "keepOriginalSound",
                                 "imageCount", "quality", "imageFidelity", "cameraControl"):
                av2 = a.get("allowedValues")
                keys.append("%s%s" % (a["name"], ("=" + "/".join(map(str, av2))) if av2 else ""))
        ins = [i.get("name") for i in (m.get("inputs") or [])]
        print("  - %-26s %s" % (m.get("model"), al))
        print("      in: %s" % ", ".join(ins))
        if keys:
            print("      arg: %s" % ", ".join(keys))
