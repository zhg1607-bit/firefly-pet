# -*- coding: utf-8 -*-
"""build_jimeng_prompts.py —— 把 106 个动作提示词压缩成「即梦 AI 视频生成」可粘贴的精简版。

即梦输入框有长度限制，且「图生视频/首尾帧」模式下首帧图已经固定了角色长相与构图，
因此每条只需要：① 简短角色锚定 ② 绿幕与构图约束 ③ 该动作的按秒分镜。

输入：dsh-pet-custom/prompts/actions/NNN-<标题>.txt
输出：dsh-pet-custom/jimeng-prompts/NNN-<标题>.txt
      dsh-pet-custom/report/jimeng_prompts_index.md（长度统计 + 优先级清单）
"""
import sys
import re
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(r"D:\wd\deepseek-harness\default-workspace\dsh-pet-custom")
SRC = ROOT / "prompts" / "actions"
DST = ROOT / "jimeng-prompts"
DST.mkdir(exist_ok=True)

# 精简角色锚定（与 character/reference.png 一致，即梦只需关键词，细节靠首帧图）
CHAR = (
    "Q版银白长发少女（与上传图片中的角色完全一致）：银白色蓬松长卷发过腰，"
    "黑色宽发箍正面有薄荷绿菱形纹，两侧白色小云朵发夹，左耳侧薄荷绿叶片发饰配深蓝蝴蝶结；"
    "紫粉色→浅蓝色渐变大眼；深蓝黑色短披风斗篷、内衬薄荷绿下摆、胸前金色底座橙色蝶翼宝石胸针；"
    "白色短袖衬衫配荷叶袖口，浅绿渐变裙摆，深蓝黑过膝长筒袜、青绿翻边配橙色蝴蝶结、深色短靴。"
    "二头身Q版比例，萌系国漫描边风格。"
)

FRAME = (
    "【画面与构图强制约束】保持与首帧图完全相同的角色长相、发型、服装配色、大小与位置；"
    "背景全程为纯绿色 #00FF00 单一色块，无阴影、无渐变、无地面、无杂物、无文字、无水印；"
    "角色居中，头顶约在画面 20% 高度、脚底约在 85% 高度，左右各留 10% 以上绿色缓冲区；"
    "角色双脚落点固定在画面正中央，全程不允许 X/Y 轴平移；"
    "任何身体部位或道具都不得触碰或超出画幅边缘；动作在画幅内部完成，无镜头运动、无变焦。"
)


def split_action(text: str):
    """返回 (标题, 正文) —— 正文取最后一个 '## ' 小节。"""
    parts = re.split(r"\n(?=## )", text)
    last = parts[-1]
    m = re.match(r"##\s+(.+)", last)
    title = m.group(1).strip() if m else "未命名"
    body = last[m.end():] if m else last
    body = body.split("\n---")[0].strip()
    body = body.replace("**动作概述**", "动作概述：").replace("**按秒分割画面**", "\n按秒分镜：")
    body = re.sub(r"\n{3,}", "\n\n", body)
    return title, body


def build(body: str) -> str:
    return (
        f"【角色】{CHAR}\n\n"
        f"{FRAME}\n\n"
        f"【本段动作｜总时长 10 秒】\n{body}\n\n"
        "【首尾帧】第 0 秒必须与首帧图完全一致（标准正面站立、画面干净无道具）；"
        "第 10 秒结束时彻底恢复到与首帧图完全一致的标准正面站立姿态，无任何道具或特效残留。"
    )


files = sorted(SRC.glob("*.txt"))
rows = []
for f in files:
    title, body = split_action(f.read_text(encoding="utf-8"))
    prompt = build(body)
    (DST / f.name).write_text(prompt, encoding="utf-8")
    rows.append((f.stem, title, len(body), len(prompt)))

lens = [r[3] for r in rows]
print(f"共 {len(rows)} 条 → {DST}")
print(f"长度 min={min(lens)} max={max(lens)} avg={sum(lens)/len(lens):.0f} 字符")

# 小批量优先级：先做「关键交互/缺口」动作
PRIORITY = ["待机呼吸休闲", "点击回应-开心跃动", "被鼠标拖拽悬空反馈", "东张西望",
            "原地漂浮踏步", "点击回应-害羞惊讶", "点击回应-傲娇生气", "点击回应-挠痒咯咯笑",
            "点击回应-元气挥手", "原地左转奔跑", "螃蟹走路"]
idx = {t: i + 1 for i, t in enumerate(PRIORITY)}
order = [r for r in rows if r[1] in idx]
order.sort(key=lambda r: idx[r[1]])

lines = ["# 即梦 AI 精简提示词索引", "",
         f"- 生成脚本：`tools/build_jimeng_prompts.py`，产物目录 `jimeng-prompts/`（{len(rows)} 条）",
         f"- 长度：min {min(lens)} / max {max(lens)} / avg {sum(lens)/len(lens):.0f} 字符",
         "- 用法：即梦 → 视频生成 → 上传 `character/first_frame_green.png` 作首帧（首尾帧模式首尾都用它）→ 粘贴对应 txt → 时长 10s → 720P → 生成", "",
         "## 小批量优先级（先做这几条补齐缺口）", "",
         "| 顺序 | 文件 | 动作名 | 提示词长度 |", "| --- | --- | --- | --- |"]
for i, r in enumerate(order, 1):
    lines.append(f"| {i} | `jimeng-prompts/{r[0]}.txt` | {r[1]} | {r[3]} |")
lines += ["", "## 全量清单", "", "| 文件 | 动作名 | 提示词长度 |", "| --- | --- | --- |"]
for r in rows:
    lines.append(f"| `jimeng-prompts/{r[0]}.txt` | {r[1]} | {r[3]} |")
(ROOT / "report" / "jimeng_prompts_index.md").write_text("\n".join(lines), encoding="utf-8")
print("written report/jimeng_prompts_index.md")
