# -*- coding: utf-8 -*-
"""kling_poll.py —— 轮询一个可灵 generationId 直到完成，并把结果存成 JSON。

用法：python tools/kling_poll.py <generationId> [最长秒数] [保存路径]
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NODE = Path(r"C:\Users\PC-7020\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe")
CLI = ROOT / ".tools" / "kling-cli" / "package" / "dist" / "cli.js"

sys.stdout.reconfigure(encoding="utf-8")


def kling(*args):
    env = dict(os.environ)
    env.pop("ELECTRON_RUN_AS_NODE", None)
    p = subprocess.run([str(NODE), str(CLI), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="ignore", env=env, timeout=300)
    out = (p.stdout or "").strip()
    i = out.find("{")
    j = out.rfind("}")
    if i >= 0 and j > i:
        try:
            return json.loads(out[i:j + 1])
        except Exception:
            pass
    return {"_raw": out[-800:], "_err": (p.stderr or "")[-400:], "_rc": p.returncode}


def main():
    gid = sys.argv[1]
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 900
    save = Path(sys.argv[3]) if len(sys.argv) > 3 else ROOT / "work" / "kling-task.json"
    t0 = time.time()
    last = None
    while time.time() - t0 < budget:
        d = kling("query_tasks", gid)
        body = d.get("body", d)
        st = body.get("status") or body.get("taskStatus")
        el = int(time.time() - t0)
        print("[%4ds] status=%s" % (el, st), flush=True)
        last = d
        if st in ("SUCCEED", "SUCCESS", "SUCCEEDED", "FAILED", "FAIL", "ERROR"):
            break
        time.sleep(20)
    save.write_text(json.dumps(last, ensure_ascii=False, indent=1), encoding="utf-8")
    body = last.get("body", last)
    print("final status:", body.get("status"))
    print("works:", json.dumps(body.get("works") or body.get("taskResult") or {}, ensure_ascii=False)[:1200])
    print("saved:", save)


if __name__ == "__main__":
    main()
