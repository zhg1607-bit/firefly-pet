"""校验 银白少女-config.jsonc：JSON 合法性 + 配置里的动作名是否与 jimeng-prompts 的 106 个动作完全对齐。"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "pet-config" / "银白少女-config.jsonc"
PROMPT_DIR = ROOT / "jimeng-prompts"


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


raw = CFG.read_text(encoding="utf-8")
cfg = json.loads(strip_jsonc(raw))
print(f"JSON 解析 OK：{CFG.name}")

anim = cfg["animations"]
names: list[str] = []
names += anim["idle"]
names += anim["turn"]
names += anim["drag"]
names += anim["clicks"]
names += [m["name"] for m in anim["moves"]["actions"]]
cat_total = 0
for cat in anim["categories"]:
    names += cat["actions"]
    cat_total += cat["weight"]
    print(f"  分类[{cat['id']}] weight={cat['weight']} 动作 {len(cat['actions'])} 个"
          + ("  noMirror" if cat.get("noMirror") else ""))
for key, arr in anim["events"].items():
    names += arr
    print(f"  事件[{key}] 档位 {len(arr)} 个")

print(f"分类池 weight 合计 = {cat_total}（应为 80）")
print(f"配置引用动作总数（含重复计）= {len(names)}  去重 = {len(set(names))}")

want = []
for p in sorted(PROMPT_DIR.glob("*.txt")):
    m = re.match(r"(\d+)-(.+)\.txt$", p.name)
    if m:
        want.append(m.group(2))

dup = sorted({n for n in names if names.count(n) > 1})
missing = [n for n in want if n not in names]          # 有素材但配置没引用
extra = [n for n in set(names) if n not in want]        # 配置引用了但没有素材

print()
print(f"素材动作数 = {len(want)}")
print(f"配置漏引用（有素材）  = {len(missing)}  {missing}")
print(f"配置多余（无素材）    = {len(extra)}  {extra}")
print(f"重复引用              = {len(dup)}  {dup}")
print()
print("结论：" + ("完全对齐 ✅" if not missing and not extra and not dup else "有问题 ❌"))
sys.exit(0 if not missing and not extra and not dup else 1)
