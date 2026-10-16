#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
即梦画布 CLI 批量驱动（银白少女桌宠动作视频）
--------------------------------------------------
用法（统一先清掉 ELECTRON_RUN_AS_NODE，脚本内部已处理）：

  python tools/jimeng_cli_batch.py list                 # 列出 11 条 ★ 高频动作与状态
  python tools/jimeng_cli_batch.py create [--all]       # 建节点 + 报价（免费）
  python tools/jimeng_cli_batch.py run    [--all] [--ceiling 200]   # 确认积分 + 提交（要钱）
  python tools/jimeng_cli_batch.py poll                 # 查状态（免费）
  python tools/jimeng_cli_batch.py download             # 下载已完成的视频到 video/
  python tools/jimeng_cli_batch.py verify               # ffprobe 校验 + 汇总

状态存在 work/cli-nodes.json，可反复重跑（幂等）。
"""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
EXE = Path(os.environ.get("DREAMINA_CANVAS_EXE", r"C:\Users\PC-7020\bin\dreamina-canvas.exe"))
WORK = ROOT / "work"
STATE = WORK / "cli-nodes.json"
PROMPT_DIR = ROOT / "jimeng-prompts"
VIDEO_DIR = ROOT / "video"
PROJECT = (WORK / "cli-project.txt").read_text(encoding="utf-8").strip()
RES_FIRST = (WORK / "cli-res-firstframe.txt").read_text(encoding="utf-8").strip()
RES_LAST = (WORK / "cli-res-lastframe.txt").read_text(encoding="utf-8").strip()

# 11 条 ★ 高频动作（与 report/jimeng_manual_checklist.md 一致）
STAR = [
    "待机呼吸休闲",
    "原地漂浮踏步",
    "点击回应-开心跃动",
    "点击回应-害羞惊讶",
    "点击回应-傲娇生气",
    "被鼠标拖拽悬空反馈",
    "螃蟹走路",
    "东张西望",
    "原地左转奔跑",
    "点击回应-挠痒咯咯笑",
    "点击回应-元气挥手",
]


def cli(*args, timeout=600):
    env = dict(os.environ)
    env.pop("ELECTRON_RUN_AS_NODE", None)
    p = subprocess.run(
        [str(EXE), "--format", "json", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=timeout,
    )
    out = (p.stdout or "").strip()
    try:
        return json.loads(out), p.returncode, (p.stderr or "").strip()
    except json.JSONDecodeError:
        return {"ok": False, "raw": out}, p.returncode, (p.stderr or "").strip()


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {}


def save_state(st):
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def prompt_file(name):
    hits = sorted(PROMPT_DIR.glob(f"*-{name}.txt"))
    if not hits:
        raise SystemExit(f"找不到提示词文件：{name}")
    return hits[0]


def targets(all_actions=False):
    if all_actions:
        return [p.stem.split("-", 1)[1] for p in sorted(PROMPT_DIR.glob("*.txt"))]
    return STAR


def cmd_list(st):
    for i, name in enumerate(STAR, 1):
        rec = st.get(name, {})
        print(f"{i:>2}. {name:<20} node={rec.get('nodeId','-'):<18} "
              f"quote={rec.get('maxCredits','-'):<5} state={rec.get('state','-'):<10} "
              f"res={rec.get('resourceId','-')}")


def cmd_create(st, all_actions=False):
    for name in targets(all_actions):
        rec = st.setdefault(name, {})
        prompt = prompt_file(name).read_text(encoding="utf-8").strip()
        if rec.get("nodeId"):
            print(f"[跳过] {name} 已有节点 {rec['nodeId']}")
            continue
        data, rc, err = cli(
            "node", "create", "video",
            "--project-id", PROJECT,
            "--model", "seedance_2.5",
            "--mode", "first_last_frame",
            "--title", prompt_file(name).stem,
            "--ratio", "16:9", "--resolution", "720p",
            "--duration", "10", "--count", "1",
            "--ref", f"res:{RES_FIRST}", "--ref", f"res:{RES_LAST}",
            "--prompt", prompt, "--dry-run",
        )
        if not data.get("ok"):
            print(f"[失败] {name} dry-run: {json.dumps(data, ensure_ascii=False)[:300]}")
            continue
        data, rc, err = cli(
            "node", "create", "video",
            "--project-id", PROJECT,
            "--model", "seedance_2.5",
            "--mode", "first_last_frame",
            "--title", prompt_file(name).stem,
            "--ratio", "16:9", "--resolution", "720p",
            "--duration", "10", "--count", "1",
            "--ref", f"res:{RES_FIRST}", "--ref", f"res:{RES_LAST}",
            "--prompt", prompt,
        )
        if not data.get("ok"):
            print(f"[失败] {name} create: {json.dumps(data, ensure_ascii=False)[:300]}")
            continue
        node = data["data"]["node"]
        rec["nodeId"] = node["nodeId"]
        rec["title"] = node.get("title")
        rec["state"] = node.get("status")
        q, _, _ = cli("node", "quote", "--node-id", rec["nodeId"], "--project-id", PROJECT)
        if q.get("ok"):
            rec["maxCredits"] = q["data"].get("totalMaxCredits")
        save_state(st)
        print(f"[建节点] {name} -> {rec['nodeId']} 报价上限 {rec.get('maxCredits')}")
    save_state(st)


def cmd_run(st, ceiling=200, all_actions=False):
    for name in targets(all_actions):
        rec = st.get(name)
        if not rec or not rec.get("nodeId"):
            print(f"[跳过] {name} 未建节点")
            continue
        if rec.get("submitId"):
            print(f"[跳过] {name} 已提交 {rec['submitId']}")
            continue
        c, _, _ = cli("node", "confirm", "--node-id", rec["nodeId"],
                      "--project-id", PROJECT, "--credit-ceiling", str(ceiling), "--yes")
        if not c.get("ok"):
            print(f"[失败] {name} confirm: {json.dumps(c, ensure_ascii=False)[:300]}")
            continue
        tok = c["data"].get("creditConfirmationToken")
        r, _, _ = cli("node", "run", "--node-id", rec["nodeId"], "--project-id", PROJECT,
                      "--credit-token", tok, "--yes")
        if not r.get("ok"):
            print(f"[失败] {name} run: {json.dumps(r, ensure_ascii=False)[:300]}")
            continue
        item = r["data"]["items"][0]
        rec["submitId"] = item.get("submitId")
        rec["state"] = item.get("state")
        if item.get("resources"):
            rec["resourceId"] = item["resources"][0].get("resourceId")
        save_state(st)
        print(f"[已提交] {name} submit={rec['submitId']} res={rec.get('resourceId')}")


def cmd_poll(st):
    for name, rec in st.items():
        if not rec.get("submitId"):
            continue
        s, _, _ = cli("operation", "status", rec["submitId"], "--project-id", PROJECT)
        if s.get("ok"):
            d = s["data"]
            rec["state"] = d.get("state") or d.get("status")
            print(f"{name:<20} {rec['state']}")
    save_state(st)


def cmd_download(st):
    VIDEO_DIR.mkdir(exist_ok=True)
    for name, rec in st.items():
        rid = rec.get("resourceId")
        if not rid:
            continue
        dst = VIDEO_DIR / f"{name}.mp4"
        if dst.exists():
            print(f"[跳过] {name} 已存在 {dst.name}")
            continue
        out, rc, err = cli("resource", "download", rid, "--project-id", PROJECT, "-o", str(dst), timeout=900)
        print(f"[下载] {name} -> {dst.name} rc={rc} {json.dumps(out, ensure_ascii=False)[:160]}")
    save_state(st)


def cmd_verify(st):
    ffprobe = ROOT / ".tools" / "ffmpeg-9.0.1-essentials_build" / "bin" / "ffprobe.exe"
    for name, rec in st.items():
        dst = VIDEO_DIR / f"{name}.mp4"
        if not dst.exists():
            continue
        p = subprocess.run([str(ffprobe), "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=width,height,r_frame_rate,nb_frames",
                            "-show_entries", "format=duration,size",
                            "-of", "json", str(dst)], capture_output=True, text=True, encoding="utf-8")
        info = json.loads(p.stdout or "{}")
        s = (info.get("streams") or [{}])[0]
        f = info.get("format") or {}
        print(f"{name:<20} {s.get('width')}x{s.get('height')} {s.get('r_frame_rate')} "
              f"frames={s.get('nb_frames')} dur={f.get('duration')} size={f.get('size')}")


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    cmd = argv[0]
    all_actions = "--all" in argv
    ceiling = 200
    if "--ceiling" in argv:
        ceiling = int(argv[argv.index("--ceiling") + 1])
    st = load_state()
    if cmd == "list":
        cmd_list(st)
    elif cmd == "create":
        cmd_create(st, all_actions)
    elif cmd == "run":
        cmd_run(st, ceiling, all_actions)
    elif cmd == "poll":
        cmd_poll(st)
    elif cmd == "download":
        cmd_download(st)
    elif cmd == "verify":
        cmd_verify(st)
    else:
        raise SystemExit(f"未知命令：{cmd}")


if __name__ == "__main__":
    main()
