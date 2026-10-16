# -*- coding: utf-8 -*-
r"""kling_batch.py —— 可灵批量出片驱动（提交 / 轮询 / 下载 / 记账）。

用法：
  python tools/kling_batch.py submit 待机呼吸休闲 东张西望 ...   # 提交（每个约 30 积分 / 10 秒 720p）
  python tools/kling_batch.py status                            # 查询所有在途任务
  python tools/kling_batch.py fetch                             # 下载所有已完成任务的无水印原片
  python tools/kling_batch.py list                              # 列出状态文件

状态文件：work\kling-jobs.json
原片落地：kling\<序号>-<动作名>.mp4（同时存封面 jpg）
提示词来源：jimeng-prompts\<序号>-<动作名>.txt
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NODE = Path(r"C:\Users\PC-7020\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\node\bin\node.exe")
CLI = ROOT / ".tools" / "kling-cli" / "package" / "dist" / "cli.js"
STATE = ROOT / "work" / "kling-jobs.json"
OUTDIR = ROOT / "kling"
FRAME = ROOT / "character" / "first_frame_green.png"
MODEL = "kling-video-v2_5"
sys.stdout.reconfigure(encoding="utf-8")


def load():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {}


def save(d):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def kling(*args, timeout=900):
    env = dict(os.environ)
    env.pop("ELECTRON_RUN_AS_NODE", None)
    p = subprocess.run([str(NODE), str(CLI), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="ignore", env=env, timeout=timeout)
    out = (p.stdout or "")
    i, j = out.find("{"), out.rfind("}")
    if i >= 0 and j > i:
        try:
            return json.loads(out[i:j + 1])
        except Exception:
            pass
    return {"_raw": out[-600:], "_err": (p.stderr or "")[-400:], "_rc": p.returncode}


def find_prompt(name):
    for p in sorted((ROOT / "jimeng-prompts").glob("*.txt")):
        if p.stem.endswith(name) or p.stem == name:
            return p
    return None


def submit(names):
    st = load()
    for name in names:
        pf = find_prompt(name)
        if pf is None:
            print("  [skip] 找不到提示词:", name)
            continue
        prompt = pf.read_text(encoding="utf-8").replace("\r\n", "\n")
        print("  提交 %s（%d 字）..." % (name, len(prompt)), flush=True)
        d = kling("image_to_video", "--model", MODEL, "--image", str(FRAME),
                  "--duration", "10", "--resolution", "720p", "--enable_audio", "false",
                  "--prompt", prompt)
        body = d.get("body", {})
        gid = body.get("generationId") or body.get("generation_id")
        st[name] = {"file": pf.stem, "generationId": gid, "status": body.get("status") or d.get("status"),
                    "credits": body.get("creditsConsumed") or body.get("credits_consumed"),
                    "submittedAt": time.strftime("%Y-%m-%d %H:%M:%S"), "ok": bool(gid)}
        if not gid:
            print("    !! 失败:", json.dumps(d, ensure_ascii=False)[:300])
        else:
            print("    ok generationId=%s credits=%s" % (gid, st[name]["credits"]))
        save(st)
        time.sleep(1)
    return st


def status():
    st = load()
    for name, j in st.items():
        gid = j.get("generationId")
        if not gid:
            continue
        d = kling("query_tasks", gid)
        b = d.get("body", {})
        j["status"] = b.get("status") or j.get("status")
        ws = b.get("works") or []
        if ws:
            j["videoUrl"] = ws[0].get("urlWithoutWatermark") or ws[0].get("url")
            j["coverUrl"] = ws[0].get("coverUrlWithoutWatermark") or ws[0].get("coverUrl")
        print("  %-22s %-12s %s" % (name, j["status"], gid[:18]))
        save(st)
    return st


def fetch():
    st = load()
    OUTDIR.mkdir(parents=True, exist_ok=True)
    for name, j in st.items():
        if j.get("status") != "COMPLETED" or j.get("downloaded") or not j.get("videoUrl"):
            continue
        num = j.get("file", "").split("-")[0]
        dst = OUTDIR / ("%s-%s.mp4" % (num, name))
        try:
            req = urllib.request.Request(j["videoUrl"], headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=600) as r:
                dst.write_bytes(r.read())
            cv = OUTDIR / ("%s-%s.cover.jpg" % (num, name))
            if j.get("coverUrl"):
                req = urllib.request.Request(j["coverUrl"], headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=600) as r:
                    cv.write_bytes(r.read())
            j["downloaded"] = str(dst)
            print("  下载 %s  %.1f MB" % (dst.name, dst.stat().st_size / 1048576))
            save(st)
        except Exception as e:
            print("  下载失败 %s: %s" % (name, e))


def wait_all(interval=30, rounds=50):
    """轮询到所有任务进入终态（COMPLETED / FAILED），随后下载已完成的无水印原片。"""
    done = {"COMPLETED", "FAILED", "failed", "completed"}
    for r in range(rounds):
        st = status()
        pend = [n for n, j in st.items() if j.get("generationId") and j.get("status") not in done]
        print("  [%d/%d] 在途 %d 条：%s" % (r + 1, rounds, len(pend), "、".join(pend) if pend else "无"))
        if not pend:
            break
        time.sleep(interval)
    print("--- 下载 ---")
    fetch()
    st = load()
    ok = [n for n, j in st.items() if j.get("status") == "COMPLETED"]
    bad = [n for n, j in st.items() if j.get("status") not in done]
    print("完成 %d 条，失败/在途 %d 条" % (len(ok), len(bad)))
    for n in bad:
        print("  !!", n, st[n].get("status"))
    return st


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "submit":
        submit(sys.argv[2:])
    elif cmd == "status":
        status()
    elif cmd == "fetch":
        status()
        fetch()
    elif cmd == "wait":
        wait_all()
    else:
        st = load()
        for name, j in st.items():
            print("%-22s %-12s credits=%s downloaded=%s" % (name, j.get("status"), j.get("credits"), bool(j.get("downloaded"))))


if __name__ == "__main__":
    main()
