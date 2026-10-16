#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
即梦内容审核三连诊断（用户批准的小批量诊断）
--------------------------------------------------
对三张候选首帧图各跑一条 480p / 4 秒 / seedance_2.5 的最短生成，只看「能不能过审」：

  A character  角色原图        character/first_frame_green.png
  B nolegs     无腿版          work/char_nolegs_frame.png
  C longskirt  长裙版          work/char_longskirt_frame.png

每条：上传 → 建节点（单首帧引用）→ 报价 → 批准(上限 200) → 提交 → 等终态 → 报告
失败（errorCode）不扣积分；成功才计费。结果写 report/audit_probe.md

用法：python tools/jimeng_audit_probe.py [--only A|B|C]
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
EXE = Path(os.environ.get("DREAMINA_CANVAS_EXE", r"C:\Users\PC-7020\bin\dreamina-canvas.exe"))
WORK = ROOT / "work"
PROJECT = (WORK / "cli-project.txt").read_text(encoding="utf-8").strip()
STATE = WORK / "cli-audit-probe.json"
REPORT = ROOT / "report" / "audit_probe.md"

CANDIDATES = [
    ("A", "character", "角色原图（短裙+过膝长筒袜）", ROOT / "character" / "first_frame_green.png"),
    ("B", "nolegs", "无腿版（下半身裁掉）", WORK / "char_nolegs_frame.png"),
    ("C", "longskirt", "长裙版（裙摆盖住双腿，只留靴子）", WORK / "char_longskirt_frame.png"),
]

PROMPT = (WORK / "testprompt1.txt")


def cli(*args, timeout=900):
    env = dict(os.environ)
    env.pop("ELECTRON_RUN_AS_NODE", None)
    p = subprocess.run([str(EXE), "--format", "json", *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env, timeout=timeout)
    out = (p.stdout or "").strip()
    try:
        return json.loads(out), p.returncode
    except json.JSONDecodeError:
        return {"ok": False, "raw": out[:500]}, p.returncode


def run_one(tag, label, desc, img, state):
    print(f"\n{'='*70}\n[{tag}] {label} — {desc}\n{'='*70}")
    rec = state.setdefault(tag, {"label": label, "desc": desc})
    if not img.exists():
        print(f"  跳过：找不到 {img}")
        rec["result"] = "missing-image"
        return
    print(f"  图: {img.name} ({img.stat().st_size} B)")
    if not rec.get("resourceId"):
        d, rc = cli("resource", "upload", "--file", str(img), "--project-id", PROJECT,
                    "--name", f"audit-{label}")
        if not d.get("ok"):
            print(f"  上传失败: {json.dumps(d, ensure_ascii=False)[:300]}")
            rec["result"] = "upload-failed"
            return
        rec["resourceId"] = d["data"]["resourceId"]
        print(f"  上传成功 resourceId={rec['resourceId']}")
    if not rec.get("nodeId"):
        prompt = PROMPT.read_text(encoding="utf-8").strip()
        d, rc = cli("node", "create", "video", "--project-id", PROJECT,
                    "--model", "seedance_2.5", "--mode", "first_last_frame",
                    "--title", f"audit-{label}", "--ratio", "16:9", "--resolution", "480p",
                    "--duration", "4", "--count", "1",
                    "--ref", f"res:{rec['resourceId']}", "--prompt", prompt)
        if not d.get("ok"):
            print(f"  建节点失败: {json.dumps(d, ensure_ascii=False)[:300]}")
            rec["result"] = "create-failed"
            return
        rec["nodeId"] = d["data"]["node"]["nodeId"]
        print(f"  节点 {rec['nodeId']}")
    if not rec.get("submitId"):
        q, _ = cli("node", "quote", "--node-id", rec["nodeId"], "--project-id", PROJECT)
        rec["quote"] = (q.get("data") or {}).get("totalMaxCredits")
        c, _ = cli("node", "confirm", "--node-id", rec["nodeId"], "--project-id", PROJECT,
                   "--credit-ceiling", "200", "--yes")
        if not c.get("ok"):
            print(f"  批准失败: {json.dumps(c, ensure_ascii=False)[:300]}")
            rec["result"] = "confirm-failed"
            return
        tok = c["data"]["creditConfirmationToken"]
        r, _ = cli("node", "run", "--node-id", rec["nodeId"], "--project-id", PROJECT,
                   "--credit-token", tok, "--yes")
        if not r.get("ok"):
            print(f"  提交失败: {json.dumps(r, ensure_ascii=False)[:300]}")
            rec["result"] = "run-failed"
            return
        item = r["data"]["items"][0]
        rec["submitId"] = item.get("submitId")
        rec["resourceId_out"] = (item.get("resources") or [{}])[0].get("resourceId")
        print(f"  已提交 submit={rec['submitId']} 报价上限={rec.get('quote')}")
    print("  等待终态…")
    w, _ = cli("operation", "wait", rec["submitId"], "--project-id", PROJECT, timeout=1800)
    data = w.get("data") or {}
    rec["state"] = data.get("state")
    errs = [r.get("serviceCode") for r in (data.get("resources") or []) if r.get("serviceCode")]
    rec["serviceCode"] = errs[0] if errs else None
    if rec["state"] == "success":
        rec["result"] = "PASS"
        print(f"  ✅ 通过！state={rec['state']}")
        rid = (data.get("resources") or [{}])[0].get("resourceId") or rec.get("resourceId_out")
        out = WORK / f"audit_{label}.mp4"
        dl, _ = cli("resource", "download", rid, "--project-id", PROJECT, "-o", str(out))
        print(f"  下载 → {out.name} ok={dl.get('ok')}")
    else:
        rec["result"] = "BLOCKED"
        print(f"  ❌ 被拦 state={rec['state']} serviceCode={rec.get('serviceCode')}")
    save(state)


def save(state):
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1].upper()
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    t0 = time.time()
    for tag, label, desc, img in CANDIDATES:
        if only and tag != only:
            continue
        try:
            run_one(tag, label, desc, img, state)
        except Exception as exc:  # 单条异常不中断整批
            print(f"  !! 异常: {type(exc).__name__}: {exc}")
            state.setdefault(tag, {})["result"] = f"error:{type(exc).__name__}"
            save(state)
    # 汇总报告
    lines = ["# 即梦审核三连诊断结果", "",
             f"- 画布：{PROJECT}", "- 规格：seedance_2.5 / first_last_frame / 480p / 4 秒 / 单首帧引用",
             f"- 提示词：work/testprompt1.txt（60 字中性版）", "",
             "| 组 | 形象 | 结果 | state | serviceCode | 备注 |", "|---|---|---|---|---|---|"]
    for tag, label, desc, img in CANDIDATES:
        rec = state.get(tag, {})
        lines.append(f"| {tag} | {desc} | {rec.get('result','-')} | {rec.get('state','-')} | "
                     f"{rec.get('serviceCode','-')} | node={rec.get('nodeId','-')} |")
    lines += ["", f"- 耗时 {int(time.time()-t0)} 秒", ""]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n报告 → {REPORT}")
    for tag, label, desc, img in CANDIDATES:
        rec = state.get(tag, {})
        print(f"  {tag}: {rec.get('result','-')}  state={rec.get('state','-')} code={rec.get('serviceCode','-')}")


if __name__ == "__main__":
    main()
