"""verify_deploy.py —— 部署后校验：配置里的每个动画名，在宠物素材目录里都有对应 webm。

检查项：
  1) 已部署配置 JSON 合法（重复引用只作提示，事件片刻意借用别名时会出现）
  2) 每个配置动作名 → pet/银白少女-animation/<名>.webm 存在且非空
  3) 素材目录里有没有「配置没引用」的孤儿文件
  4) 表情包 pet/银白少女-memes/<键>.png 齐全
  5) 权重合计 = 100（animationWeights 的 idle+turn+move + 各分类 weight）
退出码 0 = 全部通过。
"""
import json
import sys
from pathlib import Path


def strip_jsonc(text: str) -> str:
    """去掉 // 行注释（不误伤字符串里的 //）。"""
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


PET = Path.home() / ".dsh" / "dsh-pet"
CFG = PET / "pet" / "银白少女-config.jsonc"
ANIM = PET / "pet" / "银白少女-animation"
MEMES = PET / "pet" / "银白少女-memes"

sys.stdout.reconfigure(encoding="utf-8")

cfg = json.loads(strip_jsonc(CFG.read_text(encoding="utf-8")))
anim = cfg["animations"]

names: list[str] = []
names += anim["idle"] + anim["turn"] + anim["drag"] + anim["clicks"]
names += [m["name"] for m in anim["moves"]["actions"]]
for cat in anim["categories"]:
    names += cat["actions"]
for arr in anim["events"].values():
    names += arr

dups = sorted({n for n in names if names.count(n) > 1})
uniq = set(names)
print(f"配置引用动作 {len(names)} 项，去重 {len(uniq)} 项；重复别名 {len(dups)} {dups}（仅提示）")

missing, empty = [], []
for n in sorted(uniq):
    f = ANIM / f"{n}.webm"
    if not f.exists():
        missing.append(n)
    elif f.stat().st_size < 20_000:
        empty.append((n, f.stat().st_size))

have = {p.stem for p in ANIM.glob("*.webm")}
orphan = sorted(have - uniq)

print(f"素材目录 webm 文件数 = {len(have)}")
print(f"缺失（配置有名字、无文件） = {len(missing)} {missing}")
print(f"疑似空/损坏（<20KB）        = {len(empty)} {empty}")
print(f"孤儿文件（有文件、配置没引用）= {len(orphan)} {orphan}")

cat_w = sum(c["weight"] for c in anim["categories"])
aw = cfg.get("animationWeights") or {"idle": 10, "turn": 5, "move": 5}
chain_w = int(aw.get("idle", 0)) + int(aw.get("turn", 0)) + int(aw.get("move", 0))
print(f"权重：分类合计 {cat_w} + idle{aw.get('idle', 0)} turn{aw.get('turn', 0)} move{aw.get('move', 0)} = {cat_w + chain_w}")

meme_missing = [k for k in cfg.get("memes", {}) if not (MEMES / f"{k}.png").exists()]
print(f"表情包缺失 = {len(meme_missing)} {meme_missing}")

# 不变量：随机链里的动画名绝不能出现在事件池里。
# client.js:3405 用 isEventAnim(events, 当前动画) 决定播完走哪条分支；若 idle 的名字
# 出现在事件池，每次待机播完都会被当成事件动画而直接重播待机（client.js:3423-3429），
# 永远回不到 pickNext() → 随机链（走动等）彻底失效。
chain = set(anim["idle"]) | set(anim["turn"]) | set(anim["drag"]) | set(anim["clicks"])
chain |= {m["name"] for m in anim["moves"]["actions"]}
for cat in anim["categories"]:
    chain |= set(cat["actions"])
ev = set()
for arr in anim["events"].values():
    ev |= set(arr)
overlap = sorted(chain & ev)
print(f"随机链名 ∩ 事件池名  = {len(overlap)} {overlap}（必须为空）")

# 不变量：turn 池必须非空，且转向片不能同时出现在 moves.actions 里。
# client.js:3431-3434 只在「转向动画播完」时翻朝向；turn 池空 → 朝向永远不变 →
# 宠物只朝一个方向走，到屏幕边 planMove 返回 null 后再也不走（卡死）。
# 若转向片兼任移动片，每次走完都会再翻一次朝向（镜像抖动）。
move_names = {m["name"] for m in anim["moves"]["actions"]}
turn_move_shared = sorted(set(anim["turn"]) & move_names)
if not anim["turn"]:
    print("⚠️ turn 池为空 → 宠物无法换朝向、走起来会卡在屏幕边")
print(f"转向片 ∩ 移动片      = {len(turn_move_shared)} {turn_move_shared}（必须为空）")
turn_ok = bool(anim["turn"]) and not turn_move_shared

ok = not (missing or empty or orphan or meme_missing or overlap) and (cat_w + chain_w) == 100 and turn_ok
print()
print("部署校验：" + ("全部通过 ✅" if ok else "有问题 ❌"))
sys.exit(0 if ok else 1)
