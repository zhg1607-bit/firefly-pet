# -*- coding: utf-8 -*-
"""扫描原版提示词里所有可能与「用户角色设定」冲突的名词，输出清单供人工确认。"""
import re, sys, collections, json, pathlib

SRC = pathlib.Path(r"D:\wd\deepseek-harness\default-workspace\dsh-pet-assets\prompts\action-10s.md")
OUT = pathlib.Path(r"D:\wd\deepseek-harness\default-workspace\dsh-pet-custom\report\term_scan.txt")
OUT.parent.mkdir(parents=True, exist_ok=True)

text = SRC.read_text(encoding="utf-8")
lines = text.split("\n")

# 候选冲突词（原版角色特征 / 服装 / 海洋元素）
CAND = [
    "蓝发", "女仆", "鲸鱼", "尾巴", "鱼鳍", "鱼尾", "鳍", "呆毛", "围裙", "荷叶边",
    "海洋", "水", "泡泡", "泡", "鱼", "海", "猫", "猫耳", "兽耳", "手套", "领结",
    "蝴蝶结", "发箍", "发带", "发饰", "裙子", "裙摆", "披风", "斗篷", "袜", "靴", "鞋",
    "水手", "制服", "蕾丝", "丝带", "长发", "短发", "银", "白", "金", "橙", "薄荷",
    "绿", "紫", "粉", "蓝", "气泡", "星星", "心", "羽毛", "翅膀", "泳", "波浪", "漂浮",
    "悬浮", "月亮", "天使", "恶魔", "花", "樱花", "扇", "伞", "书", "笔", "电脑", "手机",
]

cnt = collections.Counter()
for kw in CAND:
    cnt[kw] = text.count(kw)

# 动作标题
heads = [(i + 1, l[3:].strip()) for i, l in enumerate(lines) if l.startswith("## ")]

# 「通用前缀」段落 = 第 1 行到第一个动作标题之前
first_action_line = heads[1][0] if len(heads) > 1 else len(lines)

with OUT.open("w", encoding="utf-8") as f:
    f.write(f"文件: {SRC}\n行数: {len(lines)}  字符数: {len(text)}\n")
    f.write(f"## 小节数: {len(heads)}（含「通用前缀」1 节 → 动作 {len(heads)-1} 个）\n")
    f.write(f"通用前缀: 第 1-{first_action_line-1} 行\n\n")
    f.write("=== 动作标题清单 ===\n")
    for i, (ln, t) in enumerate(heads):
        f.write(f"{i:3d}  L{ln:<5} {t}\n")

    f.write("\n=== 候选词频次（降序） ===\n")
    for kw, n in cnt.most_common():
        if n:
            f.write(f"{kw:<8} {n}\n")

    f.write("\n=== 疑似冲突词的上下文（每词最多 3 条） ===\n")
    SUSPECT = ["围裙", "鳍", "海洋", "手套", "泡泡", "水手", "制服", "猫", "羽毛", "翅膀",
               "泳", "波浪", "天使", "恶魔", "短发", "兽耳"]
    for kw in SUSPECT:
        hits = [l for l in lines if kw in l]
        if not hits:
            continue
        f.write(f"\n--- {kw}（{len(hits)} 行）---\n")
        for l in hits[:3]:
            f.write("  " + l.strip()[:220] + "\n")
        if len(hits) > 3:
            f.write(f"  …… 另 {len(hits)-3} 行\n")

print("written", OUT)
