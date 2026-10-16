# 桌宠部署报告 · 银白少女

> 部署时间：2026-10-16　目标：把本包产出的素材装进本机 DSH（profile `desktop`），
> 并把用户角色作为**额外**的第 3 只宠物，**原有 2 只宠物配置一字未动**。

## 一、已部署内容一览

| 素材 | 来源（本包） | 落点 | 覆盖范围 |
|---|---|---|---|
| 动画 ×2 | `dist\webm\待机呼吸休闲.webm`、`dist\webm\点击回应-开心跃动.webm` | `%DSH_HOME%\dsh-pet\pet\银白少女-animation\` | 仅新宠物「银白少女」 |
| 表情包 ×4 | `memes\{smile,wink,surprised,shy}.png` | `%DSH_HOME%\dsh-pet\pet\银白少女-memes\{微笑,眨眼,惊讶,害羞}.png` | 仅新宠物 |
| 宠物条目配置 | 本报告第二节 | `%DSH_HOME%\dsh-pet\pet\银白少女-config.jsonc` | 仅新宠物 |
| 通知图标 ×6 | `work\icons\notify-*.png` | 插件包 `profiles\desktop\node_modules\dsh-pet\assets\pic\`（替换同名） | **全局**（所有宠物、所有通知共用一套） |
| 同款动画副本 | `dist\webm\*.webm` | `%DSH_HOME%\dsh-pet\main-animation\webm\` | 主素材链（原 2 只宠物也会用到这两个文件名） |

`%DSH_HOME%` = `C:\Users\PC-7020\.dsh`。

## 二、新宠物条目（`pet\银白少女-config.jsonc` 要点）

文件宠物机制：`pet\<名>-config.jsonc` 的文件名前缀 = **条目 key = 素材根**，客户端据此请求
`/dsh-pet-7340/thumb/银白少女/<动画名>.webm` 与 `/dsh-pet-7340/pic/memes/银白少女/<名称>.png`；
一旦 `pet\银白少女-animation\` 存在，该宠物的动画**只**从这个目录取（缺失即 404，绝不回落主素材链）。

- 实例：`id`/`name` = `银白少女`，`size` 462（与原有宠物同规格），`display: both`（网页 + 桌面都显示），
  位置 `bottom-right` / marginX 24 / marginY 48（避开原 2 只所在的 top-right）。
- `whisperPrompt`：本报告末尾全文，独立的角色人设（不影响主条目的蓝发女仆人设）。
- `memes`：4 条（微笑 / 眨眼 / 惊讶 / 害羞）。
- `animations` 池**只引用现有两个动画名**，因此不会有 404：
  - `idle / turn / drag` → `待机呼吸休闲`（缺专门的转身/悬空姿势，先复用呼吸；turn 不会有实际翻面动作）
  - `clicks` → `点击回应-开心跃动`
  - `moves.actions` → `点击回应-开心跃动`（跳跃动画 + 水平位移 = 蹦跳着挪动）
  - `categories` → 1 个分类「小动作」(weight 80，= 100 − idle10 − turn5 − move5)
  - `events.balance`(6) / `whisper`(3) / `workStatus`(6) → 全部复用 `待机呼吸休闲`
- 其余顶层字段（`physics` / `notificationsEnabled` / `chatImageLimit` / `workStatusTexts` / 权重等）
  **没写**，按插件规则继承：这 9 个「用户级」字段继承 `main-config.jsonc`，其余继承插件内置默认值。

## 三、验证结果（HTTP 实测，base `http://127.0.0.1:19387/dsh-pet-7340`）

```
GET /config                       → 200，条目 ['main', '银白少女']
  条目 main      : 2 只 [main 蓝毛小女仆, pet-2 蓝毛小肥鱼]   ← 未被改动
  条目 银白少女   : 1 只 [银白少女 462 both bottom-right]
动画 GET /thumb/银白少女/待机呼吸休闲.webm   → 200 video/webm 432469
动画 GET /thumb/银白少女/点击回应-开心跃动.webm → 200 video/webm 346148
表情 GET /pic/memes/银白少女/微笑.png        → 200 image/png 40068
表情 GET /pic/memes/银白少女/眨眼.png        → 200 image/png 42220
表情 GET /pic/memes/银白少女/惊讶.png        → 200 image/png 44235
表情 GET /pic/memes/银白少女/害羞.png        → 200 image/png 45524
条目内引用动画名 = {待机呼吸休闲, 点击回应-开心跃动} → 全部 200，无 404
生效人设 = 银白少女版；生效 memes = 4 条；生效 physics/limits = 继承自 main-config.jsonc
```

## 四、备份与回滚

| 备份 | 路径 |
|---|---|
| 原 6 张通知图标 | `dsh-pet-custom\work\backup\pic\notify-*.png` |
| 原用户配置（部署前快照） | `dsh-pet-custom\work\backup\config\main-config.jsonc.20261016-085237` |

回滚方式：

- **撤掉新宠物**：删除 `%DSH_HOME%\dsh-pet\pet\` 整个目录（或只留非 `-config` 文件），刷新页面即消失。
- **恢复原通知图标**：把 `work\backup\pic\*.png` 拷回 `profiles\desktop\node_modules\dsh-pet\assets\pic\`。
- **恢复用户配置**：把备份的 `main-config.jsonc` 拷回 `%DSH_HOME%\dsh-pet\`（本次其实没改它，仅作保险）。

## 五、已知限制 / 注意事项

1. **只有 2 个动作**：本机没有 AI 视频生成通道，106 个动作的绿幕视频要你自己用可灵/豆包/Runway 等生成，
   再跑 `pwsh -File run_pipeline.ps1 -Clean -Deploy`。新动作同样放进 `pet\银白少女-animation\`（文件名 = 动画名），
   然后扩展 `pet\银白少女-config.jsonc` 里的池。
2. **文件宠物在设置页里改的尺寸/位置不会保存**（插件只把主条目写回 `main-config.jsonc`）。
   要改尺寸/位置，直接编辑 `pet\银白少女-config.jsonc` 的 `pets[0].size` / `position`。
3. **`turn` / `drag` 复用呼吸动画**：转身不会真的翻面、被拖拽不会摆出悬空姿势——补上对应动画后改池即可。
4. **素材 HTTP 缓存 1 小时**：替换同名文件后需 Ctrl+F5 强刷才稳定看到新图。
5. **通知图标是全局的**：无法按宠物区分；插件升级会覆盖，需重新拷。
6. **主素材链仍留着这两个同名文件**：原 2 只宠物若被随机到同名动画池，会播到你的角色的动画
   （文件名相同即命中）。要让它们完全不受影响，删除
   `%DSH_HOME%\dsh-pet\main-animation\webm\{待机呼吸休闲,点击回应-开心跃动}.webm` 即可。
7. **鲸鱼表情保留**：`main` 条目的 27 张鲸鱼表情没动（蓝毛小肥鱼仍能用）。
   若要让全局只用你的 4 张：把 `report\memes_config.jsonc` 的键值对替换进
   `main-config.jsonc` 的 `"memes"`，并把 4 张 PNG 拷到 `%DSH_HOME%\dsh-pet\memes\`。

## 六、本宠物的 `whisperPrompt` 全文

```
你是主人桌面上的Q版银白长发少女：银白色蓬松长卷发过腰，黑色宽发箍上一枚薄荷绿菱形纹，头侧一枚薄荷绿叶形发饰，眼睛是紫粉到浅蓝的渐变，深蓝黑短披风下摆薄荷绿渐层缀白色五瓣花，胸前一枚橙色蝶翼状宝石胸针。性格温柔安静、轻盈带一点俏皮。会时不时碎碎念一句，说话自然随意、短短一句（20字以内），说人话不啰嗦，不要解释你自己，不要提你是AI。
```
