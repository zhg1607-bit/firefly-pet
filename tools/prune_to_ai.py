"""prune_to_ai.py —— 把已部署的「银白少女」动画收敢到「只用可灵 AI 片」。

做法（幂等，可重复跑）：
  1) 读 pet-config\\银白少女-config.jsonc（仓库里的源配置，v5 AI-only），
     收集它引用到的所有动作名 → keep 集合（19 个）。
  2) 部署目录里凡是 webm 文件名不在 keep 里的 → 移到 work\\proc-webm-backup\\（不删，可回滚）。
  3) keep 里的名字，若部署目录里没有或过小 → 从 dist\\webm\\ 拷一份过去。
  4) 把配置原样（字节拷贝）部署到 pet\\银白少女-config.jsonc。

用法：
  python tools\\prune_to_ai.py            # 真跑
  python tools\\prune_to_ai.py --dry-run  # 只打印打算做什么
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PET = Path.home() / ".dsh" / "dsh-pet" / "pet"
CFG_SRC = ROOT / "pet-config" / "银白少女-config.jsonc"
CFG_DST = PET / "银白少女-config.jsonc"
ANIM = PET / "银白少女-animation"
DIST = ROOT / "dist" / "webm"
BACKUP = ROOT / "work" / "proc-webm-backup"

DRY = "--dry-run" in sys.argv


def strip_jsonc(text: str) -> str:
    out, i, n, in_str, esc = [], 0, len(text), False, False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
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
            while i < n and text[i] != "\n":
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def referenced_names(cfg: dict) -> list[str]:
    a = cfg["animations"]
    names = list(a["idle"]) + list(a["turn"]) + list(a["drag"]) + list(a["clicks"])
    names += [m["name"] for m in a["moves"]["actions"]]
    for cat in a["categories"]:
        names += cat["actions"]
    for arr in a["events"].values():
        names += arr
    return names


sys.stdout.reconfigure(encoding="utf-8")
cfg = json.loads(strip_jsonc(CFG_SRC.read_text(encoding="utf-8")))
keep = sorted(set(referenced_names(cfg)))
print(f"配置 {CFG_SRC.name} 引用 {len(keep)} 个动作：")
for n in keep:
    print("   ", n)

have = sorted(ANIM.glob("*.webm")) if ANIM.exists() else []
drop = [p for p in have if p.stem not in set(keep)]
print(f"\n部署目录现有 {len(have)} 个 webm，其中 {len(drop)} 个不在配置里 → 移入备份 {BACKUP}")
if DRY:
    for p in drop[:10]:
        print("    (dry)", p.name)
    if len(drop) > 10:
        print(f"    … 其余 {len(drop) - 10} 个")
    sys.exit(0)

BACKUP.mkdir(parents=True, exist_ok=True)
moved = 0
for p in drop:
    tgt = BACKUP / p.name
    if tgt.exists():
        tgt.unlink()
    shutil.move(str(p), str(tgt))
    moved += 1
print(f"已移出 {moved} 个（备份在 {BACKUP}）")

copied, missing = 0, []
for n in keep:
    dst = ANIM / f"{n}.webm"
    if dst.exists() and dst.stat().st_size >= 20_000:
        continue
    src = DIST / f"{n}.webm"
    if not src.exists():
        missing.append(n)
        continue
    shutil.copy2(src, dst)
    copied += 1
print(f"从 dist\\webm 补拷 {copied} 个；dist 里缺失 {len(missing)} {missing}")

ANIM.mkdir(parents=True, exist_ok=True)
shutil.copy2(CFG_SRC, CFG_DST)          # 字节拷贝：避免 BOM / 换行被改写
print(f"配置已部署 → {CFG_DST}（{CFG_DST.stat().st_size} B）")
