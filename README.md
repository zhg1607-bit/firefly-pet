# 桌面宠物素材生产包 · 定制版（dsh-pet）

> 把 [dsh-pet](https://github.com/PC2005-cloud/dsh-pet) 的整套 10 秒动作提示词改写成了**你自己的角色**（银白长发披风少女），并在本机搭好一条**一键素材链**：
>
> **AI 视频工具生成绿幕 mp4 → 去水印 → 绿幕抠像 → 画布归一化 → 缩略图 → 透明 webm（VP9-alpha）→ 直接进桌宠插件播放。**
>
> 提示词共 **106 个动作 + 6 张通知图标 + 4 张表情包**，全部按你提供的角色三视图设定表（`character/reference.png`）重写过。

---

## 仓库内容速览

本仓库 = **成品 + 配方 + 工具链**：clone 下来既能直接装进 DSH 桌宠用，也能从零复现整套素材。

| 路径 | 内容 | 类型 |
| --- | --- | --- |
| `pet-config\银白少女-config.jsonc` | 桌宠配置（19 条 AI 动画的池、权重、事件映射） | 成品 |
| `dist\webm\` | **106 条透明动画成品**（VP9-alpha，2160×1215） | 成品 |
| `memes\` | 4 张表情包 PNG（微笑/眨眼/惊讶/害羞） | 成品 |
| `pic\` | 6 张系统通知图标 PNG（512×512 透明底，替换插件包内 `assets\pic\notify-*.png`） | 成品 |
| `jimeng-prompts\` | 106 个动作的**单条配方**（约 2KB/条，可直接粘进 AI 视频工具） | 配方 |
| `prompts\` | 配方合订本（`action-10s.md`）、通知图标提示词、动作名对照表 | 配方 |
| `character\` | 角色母版：绿幕首帧 `first_frame_green.png`、立绘、三视图设定表 | 配方 |
| `tools\` | 自研工具（程序化引擎 `puppet_engine.py`、批量提交、配置校验、视频体检、总览图） | 工具链 |
| `scripts\` `run_pipeline.ps1` | 素材链：去水印 → 抠像 → 归一化 → 缩略图 → 透明 webm | 工具链 |
| `report\` | 生产记录、总览图、体检表、审计报告 | 文档 |

> **没有随仓库上传的**：`video\`（AI 生成的绿幕源 mp4，约 314MB）、`step01\`~`step04\`（素材链中间产物，约 1.5GB）、`work\`（工作区）、`.tools\`（ffmpeg 二进制，约 315MB）。这些都是本地产物——`video\` 里的源片由 AI 工具产出，其余全部能由 `run_pipeline.ps1` 重新生成。

### 一键装进 DSH 桌宠

```powershell
$dst = "$env:USERPROFILE\.dsh\dsh-pet\pet"
New-Item -ItemType Directory "$dst\银白少女-animation","$dst\银白少女-memes" -Force | Out-Null
Copy-Item .\dist\webm\*.webm                 "$dst\银白少女-animation\"
Copy-Item .\memes\*.png                      "$dst\银白少女-memes\"
Copy-Item .\pet-config\银白少女-config.jsonc   "$dst\银白少女-config.jsonc"
```

装完刷新 DSH 桌面端（Ctrl+F5）即可看到「银白少女」。

配置里**只激活了 19 条可灵 AI 生成的动作**，其余 87 条程序化动画留在 `dist\webm\` 里备用——想启用就把名字加进 `animations.categories[].actions`（随机池）、`animations.clicks`（点击池）或 `animations.events.*`（事件池），改完用 `python tools\validate_config.py` + `python tools\verify_deploy.py` 校验一遍即可。**注意两个硬约束**：`animations.turn`（转身）不能为空，且**不能与 `moves` 池重名**；随机池里的名字不能同时出现在 `events` 池里（否则随机链会失效）。

---

## 目录结构

```
dsh-pet-custom\
├─ run_pipeline.ps1          一键素材链（核心入口）
├─ character\
│  ├─ reference.png          角色三视图设定表（原图，所有 AI 生成的参考基准）
│  ├─ first_frame_green.png  绿幕首帧（喂给 AI「图生视频」的起始帧）
│  ├─ front_stand.png        角色立绘（程序化引擎的角色母版）
│  └─ head.png               头部特写（表情/聚焦参考）
├─ prompts\                  改写后的提示词
│  ├─ action-10s.md          106 个 10 秒动作（合订本，含角色设定卡 + 通用前缀）
│  ├─ actions\               001-<动作名>.txt … 106-<动作名>.txt（单条可粘贴版）
│  ├─ notify-icons.md        6 张系统通知图标提示词
│  └─ 动作名对照表.md         定制动作名 ↔ 上游动作名 ↔ 推荐文件名
├─ jimeng-prompts\           106 条单动作配方（约 2KB/条，直接粘进 AI 视频工具）
├─ scripts\                  素材链脚本（上游原版 + 本包修补）
├─ .tools\                   自带 ffmpeg（脚本按这个固定路径找它）      ← 本仓库未含
├─ video\                    ① 放 AI 工具生成的 10 秒绿幕 mp4 到这里   ← 本仓库未含
├─ step01\ … step04\         ② 各阶段产物（断点续跑，可随时删）         ← 本仓库未含
├─ dist\webm\                ③ 最终透明 webm 汇总（106 条，已随仓库提供）
├─ memes\                    表情包 PNG（微笑/眨眼/惊讶/害羞）
├─ tools\                    本包自研工具（程序化引擎、批量提交、配置校验、视频体检、总览图）
└─ report\                   各种审计/对照报告与总览图
```

---

## 快速开始（三步）

### 第 0 步 · 装好桌宠插件（一次性）

```powershell
dsh plugin --profile desktop add dsh-pet
```

> 本机**已经装好了**（`dsh-pet 0.3.7`，已列入 `profiles\desktop\package.json` 的 bundles），无需重复安装。
> 真 CLI 路径：`E:\dsh\resources\runtime\cli\bin\dsh.cmd`（`C:\Users\PC-7020\.dsh\bin\dsh-tui.cmd` 只是它的 `--profile tui` 包装）。

插件装好后，你的素材放进用户目录即可**零配置覆盖**内置动画（见第 3 步）。

### 第 1 步 · 用 AI 视频工具生成绿幕视频

1. 打开 `prompts\actions\` 目录，每条 `*.txt` 文件 = 一个 10 秒动作的完整提示词（已自动拼好**角色设定卡 + 通用前缀 + 该动作**）。
2. 把 `character\reference.png` 作为**角色参考图 / 首帧参考**上传给 AI 视频工具（可灵、豆包、Runway 等）。
3. 生成出来的视频按以下规格存放：

| 项目 | 要求 |
|---|---|
| 路径 | `video\<文件名>.mp4` |
| 文件名 | **强烈建议用「原版动作名」**（见 `prompts\动作名对照表.md`），这样部署后插件零配置直接识别 |
| 画幅/时长 | 16:9，1280×720，约 10 秒 |
| 背景 | 纯绿幕 `#00FF00`，无阴影、无渐变、无杂物（提示词里的通用前缀已强制约束） |
| 首尾帧 | 第一帧 = 标准正面站立、无任何道具；最后一秒回到同一姿态（道具闭环） |

> 一次生成 106 个动作很费时，建议先挑几个（比如「待机呼吸休闲」「点头开心」「开心跳跃」）跑通全流程再批量。

### 第 2 步 · 一键跑素材链

```powershell
cd dsh-pet-custom
pwsh -File run_pipeline.ps1 -Clean -Deploy
```

脚本会自动完成：

```
① 去水印     video\*.mp4     → step01\*.mp4
② 绿幕抠像   step01\*.mp4    → step02\*.webm  （VP9-alpha 透明视频）
③ 画布归一化 step02\*.webm   → step03\*.webm  （2160×1215 画布、角色高 900px、脚底固定 1115px）
④ 缩略图     step03\*.webm   → step04\*.webm  （640×360，插件实际播放的格式）
⑤ alpha 校验 step04\*.webm
⑥ 汇总       → dist\webm\
⑦ 部署       → %DSH_HOME%\dsh-pet\main-animation\webm\   （仅 -Deploy）
```

### 第 3 步 · 让桌宠动起来

有**两条部署路线**，先想清楚「给谁换素材」：

**路线 A · 主素材链（换掉原有宠物的动画）**

```powershell
pwsh -File run_pipeline.ps1 -Clean -Deploy
```

`-Deploy` 把 `dist\webm\*.webm` 拷进 `%DSH_HOME%\dsh-pet\main-animation\webm\`。用户目录素材优先于插件包内置素材，**文件名对应上内置动画名就是零配置替换**。
注意：主配置（`main-config.jsonc`）里的**所有**宠物共用这一条主链——动画不分宠物，只按文件名区分。

手动等价命令：

```powershell
Copy-Item step04\*.webm "$env:DSH_HOME\dsh-pet\main-animation\webm\"
```

**路线 B · 文件宠物 / pet pack（独立素材 + 独立人设，给自己的角色用推荐这条）**

`%DSH_HOME%\dsh-pet\pet\` 下一个文件 = 一个条目（**文件名前缀 = 素材根 = 条目 key**，中文合法）：

```
pet\<名>-config.jsonc      ← 条目配置（pets / whisperPrompt / memes / animations 池…）
pet\<名>-animation\*.webm  ← 这只宠物专用的动画；该目录一旦存在就只查它，缺失即 404，绝不回落主链
pet\<名>-memes\*.png       ← 这只宠物专用的表情包（键 = 配置里 memes 的键）
```

文件宠物的特性：**独立人设**（`whisperPrompt`）、**独立表情包**、**独立动画池**，与主配置宠物互不干扰；但它在设置页里改的尺寸/位置**不会写盘**，要改就手改那个 `-config.jsonc`。

> 本包已用路线 B 部署好一只额外宠物「**银白少女**」，原有 2 只（蓝毛小女仆 / 蓝毛小肥鱼）配置一字未动 —— 详见 `report\deploy_pet.md`。

最后**刷新 DSH 页面（Ctrl+F5）**：配置每次请求都重读，但素材有 `max-age=3600` 的 HTTP 缓存，普通刷新可能还在用旧图。桌面端宠物若没出现，重启 DSH 桌面端。

---

## run_pipeline.ps1 参数

| 参数 | 作用 |
|---|---|
| `-Python <路径>` | 指定 python.exe。不传则自动探测（DSH 内置运行时优先，逐个真跑依赖自检） |
| `-SkipWatermark` | 跳过第 0/1 步去水印（源视频本来就没水印时用） |
| `-BlackVideo <路径>` | 纯黑参考视频路径（用于做水印蒙版），默认 `work\black_10s.mp4` |
| `-Clean` | 先清空 step01~step04、dist 再从头跑 |
| `-NoDist` | 不往 `dist\` 汇总 |
| `-Deploy` | 跑完自动拷进插件的用户素材目录 |

示例：

```powershell
pwsh -File run_pipeline.ps1                        # 增量跑（已完成的步骤自动跳过）
pwsh -File run_pipeline.ps1 -Clean -Deploy         # 干净重跑 + 部署
pwsh -File run_pipeline.ps1 -SkipWatermark -Deploy # 无自带水印的视频直接抠像
```

**断点续跑**：每一步都会检查「产物存在 + 够大 + 不比源旧 + ffprobe 能读」，已完成的文件自动跳过——批量生成视频时可以边产边跑，中断后重跑只补增量。

---

## 去水印（可选，AI 工具带水印时才有用）

AI 视频工具导出的视频常带平台水印，且绿幕背景上的水印会破坏抠像。做法：

1. 用**同一个工具**生成一段 10 秒**纯黑**视频（水印位置/大小必须与素材视频完全一致），存成 `work\black_10s.mp4`；
2. 脚本自动用 `scripts\make_mask_black.py` 把水印区域转成蒙版 `video\watermark_mask_v5.mkv`，再用最近邻填充把水印抹掉。

> 没有黑视频也没关系：脚本检测到缺蒙版时会**自动跳过第 1 步**并把源视频原样送进抠像，只是水印会残留在画面里（糊在右下角背景上，通常不影响前景角色）。用剪映/PR 自己导出、或工具本就不带水印的话，直接 `-SkipWatermark`。

---

## 动作名对照（重要）

定制版把 106 个动作全部改写成你的角色。**部署到「银白少女」pet pack 后，文件名与配置名以「定制版动作名」为准**（因为该 pet pack 用的是自己的配置文件，配置里写什么名字就找什么文件）：

- `prompts\动作名对照表.md`：三列对照（序号 | 定制动作名 | 原版动作名）；
- 有 5 个动作刻意改了名，**配置与 webm 文件名必须同时用定制版名**：

  | 原版动作名 | 定制版动作名 |
  |---|---|
  | 女仆屈膝礼仪 | 优雅屈膝礼仪 |
  | 鲸鱼吐泡泡特效 | 梦幻泡泡特效 |
  | 用鲸鱼尾巴拍打地面 | 甩动披风下摆拍地 |
  | 蓝鲸现世 | 薄荷灵蝶现世 |
  | 优雅女仆舞 | 优雅回旋舞 |

- 其余 101 个名字两版一致；
- 插件内置配置（`node_modules\dsh-pet\assets\config.jsonc`）里**本来就完整引用了全部 106 个名字**，所以 `pet-config\银白少女-config.jsonc` 直接沿用了它的官方分组（小动作 20 / 玩耍 20 / 吃什么 16 / 时节 14 / 文字 10 + 动画链 idle 10 / turn 5 / move 5 = 100）。

校验工具：

```powershell
python tools\validate_config.py   # 配置里的名字 vs jimeng-prompts 的 106 个动作，必须完全对齐
python tools\verify_deploy.py     # 部署后：配置里每个名字都要有对应的 webm，且无孤儿文件
```

改写映射一览（角色差异处理）：

| 原版（上游角色：Q版蓝发女仆+鲸鱼尾巴） | 定制版（你的角色） |
|---|---|
| 蓝发 / 蓝发女仆 | 银白长发 / 银白长发少女 |
| 鲸鱼尾巴、鱼尾 | **披风下摆与长发发梢** |
| 鱼鳍、鳍饰 | **披风肩摆** |
| 呆毛（155 处） | **额前碎发**（角色头顶是平滑波浪发，无呆毛） |
| 围裙、手套 | 披风前襟、长筒袜 |
| 海洋生物属性 | 轻盈飘逸的仙气 |
| 动物环绕（海豚/水母） | 小银兔 / 小灵蝶 |
| 「蓝鲸现世」动作 | 「**薄荷灵蝶现世**」：胸前橙色蝶翼宝石胸针发光、飞出薄荷色灵蝶 |

---

## 表情包（4 张，已部署）

`memes\` 里是从设定表底部表情参考行裁好的 4 张半身表情（微笑 / 眨眼 / 惊讶 / 害羞，保留设定表原设计的薄荷色圆角卡片底，四角透明）。

**已经部署**到「银白少女」pet pack 目录（`pet\银白少女-memes\{微笑,眨眼,惊讶,害羞}.png`），并在 `pet\银白少女-config.jsonc` 的 `memes` 字段里写好键值描述。碎碎念会随机抽 1 张配图，对话时模型按描述选图（回复末尾输出 `[图:名称]`）。

想改成「主素材链」那两只宠物也用这 4 张：拷到 `%DSH_HOME%\dsh-pet\memes\`，再把 `report\memes_config.jsonc` 的键值对并进 `main-config.jsonc` 的 `"memes"`（会**替换**掉原有的 27 张鲸鱼表情；先备份 `main-config.jsonc` 即可随时回退）。

> 想重裁（比如换了参考图）：跑 `python tools\probe_faces.py` 定位表情区域，改 `tools\make_memes.py` 里的 REGIONS 坐标再跑。

## 通知图标（6 张，成品在 `pic\`）

`prompts\notify-icons.md` = 6 张系统通知图标提示词（对话完成 / 生成失败 / 输出截断 / 权限申请 / 用户选择 / 测试），已改写为你的角色。

**成品就在本仓库** `pic\notify-{done,error,truncated,approval,question,test}.png`（512×512、透明底、同一角色同一画风），对照图见 `report\notify_icons_sheet.png`。

通知图标**没有用户目录覆盖路径**，只能替换插件包内文件，而且**插件更新/重装会把它覆盖回原版**（本机就发生过：2026-10-16 插件更新后回到了原版蓝毛小女仆图标）。安装 / 重新应用：

```powershell
$pic = "$env:USERPROFILE\.dsh\profiles\desktop\node_modules\dsh-pet\assets\pic"
if(-not (Test-Path "$pic\_original\notify-done.png")) {   # 只在第一次留原图备份
  New-Item -ItemType Directory "$pic\_original" -Force | Out-Null
  Copy-Item "$pic\notify-*.png" "$pic\_original\"
}
Copy-Item .\pic\notify-*.png $pic -Force
```

恢复原版 = 把 `$pic\_original\*.png` 拷回，或重装插件。注意这是**全局**的（所有宠物共用一套通知图标）。

---

## 环境说明 / 常见问题

**Q：提示找不到 ffmpeg？**
本包已自带（`.tools\ffmpeg-9.0.1-essentials_build\`，含 ffmpeg/ffprobe，编码器齐全）。脚本按这个**固定路径**找它，别移动；换机器时把整个 `.tools` 目录一起拷走即可。

**Q：提示找不到可用的 python？**
脚本会按「DSH 内置运行时 → 用户目录 → PATH」逐个探测，并真实跑一次 `import numpy, scipy, PIL` 自检（Windows 自带的商店占位 python.exe 会被识破跳过）。仍失败就用 `-Python` 指定，例如：
`pwsh -File run_pipeline.ps1 -Python "$env:DSH_HOME\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"`

**Q：控制台中文乱码？**
本机 PowerShell 是 5.1，`.ps1` 文件必须**带 UTF-8 BOM**（本包已带）。若你用编辑器改过 `run_pipeline.ps1` 后中文变乱码/语法报错，多半是 BOM 被去掉了——另存为「UTF-8 with BOM」即可。

**Q：alpha 校验报 `!! LOST`？**
说明成品透明通道丢了。常见原因：源视频背景不是纯 `#00FF00`（有阴影/渐变/杂物）。检查 `video\` 源文件，或单独重跑 `python scripts\check_alpha.py step04\*.webm` 定位。

**Q：角色位置/大小在插件里不对？**
第 ③ 步归一化会把每个视频缩放到统一规格（角色高 900px、脚底 y=1115，居中于 2160×1215 画布），并写出 `step03\params.json` 供核对。若角色忽大忽小，说明源视频的人物比例不一致——重新生成时严格按提示词通用前缀的位置约束（头顶 20%、脚底 85%、左右 25%/75%）执行。

**Q：中间产物能删吗？**
能。`step01~step04`、`work\`、`dist\` 都是可再生产物，`-Clean` 会清掉重跑。`video\` 是源素材、`character\` 是参考图，别删。

---

## 合成测试（本包已跑通验证）

用 `tools\make_test_videos.py` 生成了合成替身视频（纯绿幕 + Q 版小人 + 右下角假水印 + 半透明泡泡）做了端到端验证：

- 水印被最近邻填充抹掉（蒙版 16400 px/帧）→ 抠像后透明通道干净（alpha min 0 / max 255）→ 归一化后角色居中、内容边界不含水印区（`content_union x 465~813`，水印在 x 980~1250）→ 缩略图 640×360 正常。
- 结果文件：`dist\webm\test-stand.webm`（0.37 MB）。想自己复现：`python tools\make_test_videos.py` 然后 `pwsh -File run_pipeline.ps1 -Clean`。

---

## 本机全量生产记录（106 条）

本包实际产出过全套 106 个动作，来源分两类：

| 来源 | 条数 | 工具 | 说明 |
|---|---|---|---|
| AI 视频生成 | 20 | 可灵 `kling-video-v2_5`（10s / 720p / 24fps） | 11 条核心交互（待机/点击×5/拖拽/转身/走路…）+ 9 条事件（工作状态×6、碎碎念×3）；每条扣 30 积分 |
| 程序化渲染 | 86 | `tools\puppet_engine.py` | 2D 纸偶形变，纯离线免费；`--only <名字…> --jobs 3` 跑 86 条耗时 2474 s |

- **为什么不用即梦**：即梦画布对「Q 版动漫少女」类素材整体触发内容审核（`errorCode 20109`）。原图、裁掉下半身、换长裙、乃至用即梦自己的图生图重绘后再喂视频——**四种方式全部被拦**，故改用可灵。
- 可灵片子经 `tools\probe_video.py` 体检：绿幕占比 88.5~88.7%、角色 bbox 居中、**无第三方水印**，因此素材链统一加 `-SkipWatermark`。
- 程序化片子背景是精确 `#00FF00`（非近似绿色），可直接进素材链。
- 全量素材都在 `video\`（106 个 mp4）；20 条 AI 原片另有一份备份在 `work\ai-video-backup\`。

**实跑结果**：素材链 `run_pipeline.ps1 -SkipWatermark`（增量，不清场）跑通 **106/106 alpha OK**（用时 2820.5 s）→ `dist\webm` 106 个 → `tools\deploy_silver_pet.ps1` 部署到 `%USERPROFILE%\.dsh\dsh-pet\pet\银白少女-animation\`（106 个 webm）+ `银白少女-config.jsonc`（7263 B）。`tools\verify_deploy.py` 报「106 引用 / 106 文件 / 0 缺失 / 0 孤儿 / 0 重复 全部通过」；抽检 HTTP `/dsh-pet-7340/thumb/银白少女/<名>.webm` 均返回 `200 video/webm`。

> ⚠️ **踩坑记录**：本机 PowerShell 是 **5.1**，`.ps1` 文件**必须带 UTF-8 BOM**。`tools\deploy_silver_pet.ps1` 当初是用不带 BOM 的 UTF-8 写的，结果 5.1 把中文字符串的字节解码错、引号提前截断，脚本**只打印“部署 106 个 webm/完成”的日志却一个文件都没拷**（`$ErrorActionPreference='Stop'` 也没报错）。补上 BOM 后立即正常。凡是中文 `.ps1`，写完都要检查前 3 字节是 `EF BB BF`。

### 交付形态 v5：只保留 AI 动画（19 条）

106 条虽然全跑通了，但两条路线**观感差距一眼可见**（AI 片有真实的转身、位移、披风扫动；程序化片是同一张立绘的轻微形变），所以最终交付收敛为**只用可灵 AI 片**：

- **20 → 19**：`东张西望` 的可灵原片有生成事故——**t≥2s 起画面里出现 3 个克隆人**（模型把“东张西望”理解成了分身）。用 `tools\check_multifigure.py`（前景连通块分析）全量复检 106 条，只有这一条中招。修复前后对比见 `report\dongzhangxiwang_before_after.png`。
- **部署收敢**：`tools\prune_to_ai.py`（新增，幂等）按 `pet-config\银白少女-config.jsonc` 引用到的名字保留文件，其余 87 个 webm 移入 `work\proc-webm-backup\`（不删，可随时回滚）+ 重新部署配置。
- **配置 v5 的三处结构取舍**（都写进了配置文件头注释，并且用 `tools\verify_deploy.py` 的两条不变量校验兜住）：
  1. `categories: []` + `animationWeights = {idle:90, turn:5, move:5}`——80 条随机小动作全是程序化的，分类池只能空；空池合法（`pickWeightedCategory` 全空返回 null → 回落 idle）。内置给分类池的 80 份权重并入 idle，于是「走动/转向的触发频率」和内置宠物一致。
  2. `turn: ["原地左转奔跑"]`——**这条不能省**。`client.js:3511` 算移动方向用的是 `dir = (facing === "right") !== turn.includes(当前动画) ? 1 : -1`，而**换朝向只发生在转向动画播完时**（`client.js:3431-3434`）。`turn` 池一旦为空，朝向永远不变 → 宠物只朝一个方向走，撞到屏幕边后 `planMove` 返回 null、`tryMove` 返回 false，**之后再也不走（卡死）**。所以必须有一条「专属转向片」，它只能出现在 `turn` 池里；如果同时兼任 `moves.actions`，每次走完都会再翻一次朝向（镜像抖动）。这里选了 AI 片 `原地左转奔跑`（本身就是边跑边转身），并从 `moves.actions` 移除，`moves` 剩 `螃蟹走路`/`原地漂浮踏步`。
  3. `events.balance` 必须非空（插件硬校验 `balance.length > 0`，空了整份配置判非法），故 6 档余额改为**借用 AI 事件片按情绪映射**（雀跃庆祝→清点归档→思考冒泡→原地踱步张望→垂头叹气冒汗，越穷越沮丧），不再有专门的数钱/钱袋画面。余额数字本身由气泡单独显示，不受影响。
     - ⚠️ **别名只能借用「纯事件片」（`工作状态-*` / `碎碎念-*`）**，不能借 `idle`/`clicks`/`moves` 里的名字。原因在 `lib\client.js:3405`：动画播完时用 `isEventAnim(events, 当前动画)` 判断走哪条分支，若把 idle 的「待机呼吸休闲」写进任何事件池，每次待机播完都会被判成事件动画 → 直接重播待机（`client.js:3423-3429`），**永远回不到 `pickNext()` 抽下一条**，随机链彻底失效。
- **两条部署不变量**（`tools\verify_deploy.py` 已实装，报错会退出码 1）：① 「随机链名 ∩ 事件池名 = 空」；② 「`turn` 池非空 且 转向片 ∩ 移动片 = 空」。
- **最终校验**：`tools\verify_deploy.py` →「25 引用 / 19 去重 / 0 缺失 / 0 空 / 0 孤儿 / 权重 100 / 表情包 0 缺失」全部通过；HTTP 实测 19/19 返回 `200`（>20KB），已移出的 `东张西望`/`余额-*`/`吃汤圆` 等返回 `404`，`main` 两只原宠物不受影响（仍取包内鲸鱼素材）。
- **要回到 106 条**：把 `work\proc-webm-backup\` 的 87 个 webm 拷回 `银白少女-animation\`，配置换回 106 引用版即可（`dist\webm` 里 106 个 webm 仍在）。
- 全部 106 条的缩略总览见 `report\all_106_montage.png`（蓝色 `★AI` = 可灵片，灰色「程序化」= 引擎片），体检数据 `report\all_106_probe.tsv`。

---

## 附录：提示词改写细节

- 改写脚本：`tools\rewrite_prompts.py`（幂等可重跑，从上游提示词 → 本包 `prompts\`）。
- 审计报告：`report\rewrite_report.md`、`report\term_scan.txt`（词频 + 冲突词扫描）。
- 角色设定卡（12 色 hex + 禁止项负向约束）已内嵌在 `prompts\action-10s.md` 开头，每次 AI 生成都会自动带上；参考图仍是**最高优先级的角色依据**。
- 上游原版脚本与教程见 <https://github.com/PC2005-cloud/dsh-pet>（本包 `scripts\` 即上游脚本，做了两处修补：`make_mask_black.py` 参数化加速、`check_alpha.py` 修正 ffmpeg 路径与解码器）。
