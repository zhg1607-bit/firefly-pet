# 即梦 AI 精简提示词索引

- 生成脚本：`tools/build_jimeng_prompts.py`，产物目录 `jimeng-prompts/`（106 条）
- 长度：min 667 / max 2379 / avg 1455 字符
- 用法：即梦 → 视频生成 → 上传 `character/first_frame_green.png` 作首帧（首尾帧模式首尾都用它）→ 粘贴对应 txt → 时长 10s → 720P → 生成

## 小批量优先级（先做这几条补齐缺口）

| 顺序 | 文件 | 动作名 | 提示词长度 |
| --- | --- | --- | --- |
| 1 | `jimeng-prompts/001-待机呼吸休闲.txt` | 待机呼吸休闲 | 784 |
| 2 | `jimeng-prompts/004-点击回应-开心跃动.txt` | 点击回应-开心跃动 | 772 |
| 3 | `jimeng-prompts/007-被鼠标拖拽悬空反馈.txt` | 被鼠标拖拽悬空反馈 | 765 |
| 4 | `jimeng-prompts/025-东张西望.txt` | 东张西望 | 1636 |
| 5 | `jimeng-prompts/003-原地漂浮踏步.txt` | 原地漂浮踏步 | 771 |
| 6 | `jimeng-prompts/005-点击回应-害羞惊讶.txt` | 点击回应-害羞惊讶 | 762 |
| 7 | `jimeng-prompts/006-点击回应-傲娇生气.txt` | 点击回应-傲娇生气 | 813 |
| 8 | `jimeng-prompts/090-点击回应-挠痒咯咯笑.txt` | 点击回应-挠痒咯咯笑 | 1370 |
| 9 | `jimeng-prompts/091-点击回应-元气挥手.txt` | 点击回应-元气挥手 | 1386 |
| 10 | `jimeng-prompts/026-原地左转奔跑.txt` | 原地左转奔跑 | 1724 |
| 11 | `jimeng-prompts/023-螃蟹走路.txt` | 螃蟹走路 | 1207 |

## 全量清单

| 文件 | 动作名 | 提示词长度 |
| --- | --- | --- |
| `jimeng-prompts/001-待机呼吸休闲.txt` | 待机呼吸休闲 | 784 |
| `jimeng-prompts/002-原地小憩沉眠.txt` | 原地小憩沉眠 | 792 |
| `jimeng-prompts/003-原地漂浮踏步.txt` | 原地漂浮踏步 | 771 |
| `jimeng-prompts/004-点击回应-开心跃动.txt` | 点击回应-开心跃动 | 772 |
| `jimeng-prompts/005-点击回应-害羞惊讶.txt` | 点击回应-害羞惊讶 | 762 |
| `jimeng-prompts/006-点击回应-傲娇生气.txt` | 点击回应-傲娇生气 | 813 |
| `jimeng-prompts/007-被鼠标拖拽悬空反馈.txt` | 被鼠标拖拽悬空反馈 | 765 |
| `jimeng-prompts/008-优雅屈膝礼仪.txt` | 优雅屈膝礼仪 | 770 |
| `jimeng-prompts/009-梦幻泡泡特效.txt` | 梦幻泡泡特效 | 772 |
| `jimeng-prompts/010-超大伸懒腰.txt` | 超大伸懒腰 | 786 |
| `jimeng-prompts/011-小幅度原地360度旋转展示.txt` | 小幅度原地360度旋转展示 | 1648 |
| `jimeng-prompts/012-原地跳跃抓碎头顶物品.txt` | 原地跳跃抓碎头顶物品 | 700 |
| `jimeng-prompts/013-原地重力下蹲压缩.txt` | 原地重力下蹲压缩 | 667 |
| `jimeng-prompts/014-原地敲击桌面互动.txt` | 原地敲击桌面互动 | 667 |
| `jimeng-prompts/015-原地专心玩魔方.txt` | 原地专心玩魔方 | 668 |
| `jimeng-prompts/016-原地蹲下玩玩具汽车.txt` | 原地蹲下玩玩具汽车 | 678 |
| `jimeng-prompts/017-玩游戏气急败坏.txt` | 玩游戏气急败坏 | 752 |
| `jimeng-prompts/018-被吓一跳.txt` | 被吓一跳 | 808 |
| `jimeng-prompts/019-偷吃零食被抓住.txt` | 偷吃零食被抓住 | 817 |
| `jimeng-prompts/020-甩动披风下摆拍地.txt` | 甩动披风下摆拍地 | 879 |
| `jimeng-prompts/021-哈欠连天.txt` | 哈欠连天 | 810 |
| `jimeng-prompts/022-打瞌睡被惊醒.txt` | 打瞌睡被惊醒 | 1429 |
| `jimeng-prompts/023-螃蟹走路.txt` | 螃蟹走路 | 1207 |
| `jimeng-prompts/024-悠闲哼歌.txt` | 悠闲哼歌 | 1344 |
| `jimeng-prompts/025-东张西望.txt` | 东张西望 | 1636 |
| `jimeng-prompts/026-原地左转奔跑.txt` | 原地左转奔跑 | 1724 |
| `jimeng-prompts/027-玩水枪.txt` | 玩水枪 | 1655 |
| `jimeng-prompts/028-小提琴演奏.txt` | 小提琴演奏 | 1719 |
| `jimeng-prompts/029-薄荷灵蝶现世.txt` | 薄荷灵蝶现世 | 1299 |
| `jimeng-prompts/030-吃白饭.txt` | 吃白饭 | 1233 |
| `jimeng-prompts/031-深度思考碎碎念.txt` | 深度思考碎碎念 | 1083 |
| `jimeng-prompts/032-照镜子.txt` | 照镜子 | 1327 |
| `jimeng-prompts/033-优雅回旋舞.txt` | 优雅回旋舞 | 1174 |
| `jimeng-prompts/034-可爱宅舞.txt` | 可爱宅舞 | 1139 |
| `jimeng-prompts/035-轻快摇摆舞.txt` | 轻快摇摆舞 | 1161 |
| `jimeng-prompts/036-整体换装试色.txt` | 整体换装试色 | 1348 |
| `jimeng-prompts/037-大口吃零食.txt` | 大口吃零食 | 1390 |
| `jimeng-prompts/038-吹气球.txt` | 吹气球 | 1393 |
| `jimeng-prompts/039-动物环绕.txt` | 动物环绕 | 1481 |
| `jimeng-prompts/040-轻快记录.txt` | 轻快记录 | 1306 |
| `jimeng-prompts/041-写代码.txt` | 写代码 | 1521 |
| `jimeng-prompts/042-吃Token.txt` | 吃Token | 1338 |
| `jimeng-prompts/043-吃早餐.txt` | 吃早餐 | 1219 |
| `jimeng-prompts/044-吃午餐.txt` | 吃午餐 | 1384 |
| `jimeng-prompts/045-吃晚餐.txt` | 吃晚餐 | 1648 |
| `jimeng-prompts/046-放风筝.txt` | 放风筝 | 1370 |
| `jimeng-prompts/047-摇扇纳凉.txt` | 摇扇纳凉 | 1247 |
| `jimeng-prompts/048-吃冰淇淋融化.txt` | 吃冰淇淋融化 | 1334 |
| `jimeng-prompts/049-被落叶淹没.txt` | 被落叶淹没 | 1910 |
| `jimeng-prompts/050-中秋赏月吃月饼.txt` | 中秋赏月吃月饼 | 1613 |
| `jimeng-prompts/051-堆雪人.txt` | 堆雪人 | 1420 |
| `jimeng-prompts/052-放烟花.txt` | 放烟花 | 1605 |
| `jimeng-prompts/053-拆礼物.txt` | 拆礼物 | 1520 |
| `jimeng-prompts/054-吃粽子.txt` | 吃粽子 | 1684 |
| `jimeng-prompts/055-吃汤圆.txt` | 吃汤圆 | 1549 |
| `jimeng-prompts/056-吃饺子.txt` | 吃饺子 | 1589 |
| `jimeng-prompts/057-吃糖葫芦.txt` | 吃糖葫芦 | 1641 |
| `jimeng-prompts/058-吃青团.txt` | 吃青团 | 1575 |
| `jimeng-prompts/059-吃腊八粥.txt` | 吃腊八粥 | 1635 |
| `jimeng-prompts/060-吃长寿面.txt` | 吃长寿面 | 1701 |
| `jimeng-prompts/061-吃年糕.txt` | 吃年糕 | 1758 |
| `jimeng-prompts/062-吃重阳糕.txt` | 吃重阳糕 | 1674 |
| `jimeng-prompts/063-吃西瓜.txt` | 吃西瓜 | 1721 |
| `jimeng-prompts/064-涮火锅.txt` | 涮火锅 | 1855 |
| `jimeng-prompts/065-吃大闸蟹.txt` | 吃大闸蟹 | 1807 |
| `jimeng-prompts/066-是啊，吃什么.txt` | 是啊，吃什么 | 1930 |
| `jimeng-prompts/067-收红包.txt` | 收红包 | 1707 |
| `jimeng-prompts/068-舞狮头.txt` | 舞狮头 | 1756 |
| `jimeng-prompts/069-写福字.txt` | 写福字 | 1748 |
| `jimeng-prompts/070-穿针乞巧.txt` | 穿针乞巧 | 1923 |
| `jimeng-prompts/071-装点圣诞树.txt` | 装点圣诞树 | 1982 |
| `jimeng-prompts/072-讨糖南瓜灯.txt` | 讨糖南瓜灯 | 1935 |
| `jimeng-prompts/073-插茱萸赏菊.txt` | 插茱萸赏菊 | 1852 |
| `jimeng-prompts/074-放河灯.txt` | 放河灯 | 2016 |
| `jimeng-prompts/075-萌化小幽灵.txt` | 萌化小幽灵 | 2040 |
| `jimeng-prompts/076-放孔明灯.txt` | 放孔明灯 | 2096 |
| `jimeng-prompts/077-骑木马.txt` | 骑木马 | 2143 |
| `jimeng-prompts/078-变鸽子.txt` | 变鸽子 | 2030 |
| `jimeng-prompts/079-凭空生花.txt` | 凭空生花 | 1891 |
| `jimeng-prompts/080-扑克魔术.txt` | 扑克魔术 | 2086 |
| `jimeng-prompts/081-吹笛子.txt` | 吹笛子 | 2227 |
| `jimeng-prompts/082-三球抛接.txt` | 三球抛接 | 2244 |
| `jimeng-prompts/083-蝴蝶蜜蜂环绕头顶开花.txt` | 蝴蝶蜜蜂环绕头顶开花 | 2379 |
| `jimeng-prompts/084-晨间刷牙.txt` | 晨间刷牙 | 2199 |
| `jimeng-prompts/085-撸猫.txt` | 撸猫 | 2124 |
| `jimeng-prompts/086-踢毽子.txt` | 踢毽子 | 2085 |
| `jimeng-prompts/087-抽陀螺.txt` | 抽陀螺 | 2310 |
| `jimeng-prompts/088-下五子棋.txt` | 下五子棋 | 1600 |
| `jimeng-prompts/089-荡秋千.txt` | 荡秋千 | 1786 |
| `jimeng-prompts/090-点击回应-挠痒咯咯笑.txt` | 点击回应-挠痒咯咯笑 | 1370 |
| `jimeng-prompts/091-点击回应-元气挥手.txt` | 点击回应-元气挥手 | 1386 |
| `jimeng-prompts/092-余额-钱袋满溢.txt` | 余额-钱袋满溢 | 1664 |
| `jimeng-prompts/093-余额-金袋叮当.txt` | 余额-金袋叮当 | 1417 |
| `jimeng-prompts/094-余额-钱袋如常.txt` | 余额-钱袋如常 | 1296 |
| `jimeng-prompts/095-余额-数金皱眉.txt` | 余额-数金皱眉 | 1420 |
| `jimeng-prompts/096-余额-袋空如洗.txt` | 余额-袋空如洗 | 1408 |
| `jimeng-prompts/097-余额-分文不剩.txt` | 余额-分文不剩 | 1633 |
| `jimeng-prompts/098-碎碎念-擦桌碎碎念.txt` | 碎碎念-擦桌碎碎念 | 1109 |
| `jimeng-prompts/099-碎碎念-发呆碎碎念.txt` | 碎碎念-发呆碎碎念 | 1062 |
| `jimeng-prompts/100-碎碎念-对屏碎碎念.txt` | 碎碎念-对屏碎碎念 | 1009 |
| `jimeng-prompts/101-工作状态-思考冒泡.txt` | 工作状态-思考冒泡 | 1463 |
| `jimeng-prompts/102-工作状态-忙碌点按.txt` | 工作状态-忙碌点按 | 1538 |
| `jimeng-prompts/103-工作状态-清点归档.txt` | 工作状态-清点归档 | 1517 |
| `jimeng-prompts/104-工作状态-原地踱步张望.txt` | 工作状态-原地踱步张望 | 1572 |
| `jimeng-prompts/105-工作状态-雀跃庆祝.txt` | 工作状态-雀跃庆祝 | 1490 |
| `jimeng-prompts/106-工作状态-垂头叹气冒汗.txt` | 工作状态-垂头叹气冒汗 | 1562 |