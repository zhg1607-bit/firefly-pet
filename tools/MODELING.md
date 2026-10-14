# 建模工具链（本机已装好，可直接用）

这台机器上「给桌宠做模型」需要的能力已经装齐并逐项验证过。没有视觉能力时，
所有质量判断都靠下面第 4 条的客观指标 + ASCII 剪影，不靠"看起来应该对"。

## 一、装了什么

Python 用的是 DSH 自带解释器：
`C:\Users\Administrator\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`

| 包 | 版本 | 用途 |
| --- | --- | --- |
| opencv-contrib-python-headless | 5.0.0 | GrabCut 抠像、显著性与中心先验、导向滤波精修、Poisson 无缝融合、inpaint 修补、超分接口 |
| scikit-image / scipy | 0.26.0 / 1.18.1 | SSIM、PSNR 等客观画质指标 |
| vtracer | 最新 | 彩色矢量化（Rust 实现，多层彩色 SVG） |
| imagehash | 4.3.2 | 感知哈希，判断两张图"看起来像不像" |
| imageio-ffmpeg | 0.6.0 | 视频抽帧（自带 ffmpeg 二进制，系统无需另装） |
| Pillow / numpy / lxml | 已有 | 基础图像处理与 SVG 解析 |

安装命令（需要时重装）：
```
<python> -m pip install opencv-contrib-python-headless scikit-image vtracer imagehash imageio-ffmpeg
```

## 二、命令行工具：`tools/modeling.py`

```
# 1) 抠像：泛洪填充 → 显著性(带中心先验) → rect GrabCut 三级兜底，再做 GrabCut 精修 + 边缘精修
python tools/modeling.py extract <输入图> <输出.png> [--tol 26] [--grabcut 1]

# 2) 彩色矢量化（默认 cutout 分层：背景可整层剥离，得到真透明底 SVG）
python tools/modeling.py vectorize <输入.png> <输出.svg> [--precision 5] [--layer-diff 32] [--hierarchical cutout]

# 3) SVG 光栅化（Edge headless），用于验证矢量还原度
python tools/modeling.py rasterize <输入.svg> <输出.png> [--width 1832]

# 4) 客观比对：SSIM / PSNR / 不透明区 IoU / 感知哈希距离
python tools/modeling.py compare <a.png> <b.png> [--threshold 0.85]

# 5) 高质量放大（LANCZOS + 非锐化掩模）
python tools/modeling.py upscale <输入.png> <输出.png> --factor 2

# 6) 无缝移植（Poisson）：把部件/五官贴到另一张图上且不留接缝
python tools/modeling.py transplant <底图> <贴片> <输出.png> --box x,y,w,h

# 7) 修补缺口
python tools/modeling.py inpaint <输入.png> <蒙版.png> <输出.png> --radius 3
```

## 三、实测结果（都是真实跑出来的数）

**抠像**（判定：不透明区占比是否合理 + ASCII 剪影是否是完整人形）

| 输入 | 方法 | 结果 |
| --- | --- | --- |
| 白底站姿立绘 458×608 | flood | 保留 71.5%（真值 71.9%）✓ |
| 泳池场景截图 276×392 | saliency | 保留 19.6%，剪影清晰可辨（头部+身体）✓ |
| 对话场景截图 258×384 | saliency | 保留 23.1%，剪影正常 ✓ |
| 同上前提下的旧泛洪实现 | flood | 保留 91.2% —— 完全失败（背景被当前景） |

**矢量化**（目标：透明底正确 + SSIM 尽量高）

| 档位 | SVG 体积 | path 数 | 不透明区 IoU | SSIM | 判定 |
| --- | --- | --- | --- | --- | --- |
| hi (precision 6 / layer-diff 12) | 1.54 MB | 2129 | **0.9672** | 0.874 | 可用（推荐） |
| mid (5 / 32) | 973 KB | 1074 | 0.9675 | 0.847 | 可用 |
| lo (4 / 48) | 432 KB | 174 | 0.9675 | 0.770 | 轻量版 |

不透明区 IoU 0.967 = 矢量轮廓与原始 alpha 几乎重合（原始 71.8% vs 矢量 69.8%）。

## 四、踩过的坑（下次直接绕开）

1. **OpenCV 5 的 `ximgproc.guidedFilter` 传 uint8 会返回全 0** → 必须转 float32（guide 与 src 都归一化到 0~1），
   并且 `eps` 不能太小（用 ≥1e-3），否则出 NaN；两者都要兜底。
2. **`hierarchical="stacked"` 会把角色自身的白色（头发/外套）和背景画进同一层**，
   剥背景时连人一起剥掉（不透明区掉到 60%）→ 用 `hierarchical="cutout"`，各层互不重叠，背景正好是一层。
3. **纯 `GrabCut(rect)` 在动漫平涂图上会整片塌缩**（前景只剩 1.5%）→ 先用泛洪/显著性给出初始掩膜，再用 `GC_INIT_WITH_MASK` 精修。
4. **Edge `--screenshot` 的输出路径含中文会静默失败**，且新版 headless 需要 `--user-data-dir` →
   统一写到 `%TEMP%` 的纯 ASCII 路径再拷回；透明底要加 `--default-background-color=00000000`。
5. **PowerShell `Set-Content -Encoding UTF8` 会给文件加 BOM**，Python 解析 `\ufeff` 直接报错 →
   写 Python 文件用 `[System.IO.File]::WriteAllText($p, $t, (New-Object System.Text.UTF8Encoding($false)))`。
6. **这台机器的控制台是 GBK**，Python 里 print `✓`/`✗` 会 `UnicodeEncodeError` → 一律用 ASCII 标记（OK/FAIL）。
7. **比较含透明通道的图时不能直接算 SSIM**：要先各自合成到同一底色（白底）再算，
   否则透明区会污染指标（表现为各档位 IoU 完全相同，那是假数据）。

## 五、没装/不具备的能力（如实说明）

- **视觉理解**：本会话的模型不接受图片输入，modlens 也没配视觉 provider。
  所以"像不像"最终仍需人眼确认；工具链能给出的是客观指标（SSIM/IoU/剪影）而不是审美判断。
  若把模型切成支持图片的，`read_image` 就能直接看立绘、视频抽帧和上面的对比图。
- **AI 生成式建模**（如用扩散模型重绘/生成新姿势）：需要 GPU 推理栈与模型权重，未安装。
- **真 3D 建模**：桌宠是 2D 立绘，未涉及；若要做 3D 需另装 trimesh/blender 等，且需要多视角参考图。

## 六、应用记录：桌宠模型优化（用本工具链做的第一次实战）

目标：把桌宠立绘从「旧流水线抠图 + LANCZOS 放大」升级成矢量模型。

| 项目 | 旧 | 新 |
| --- | --- | --- |
| 抠像方式 | 泛洪 + 腐蚀 1px + 羽化 | 泛洪 → GrabCut 精修 → 导向滤波 |
| alpha 边缘过渡带 | 8 px（**二值，无抗锯齿**） | 9783 px（4.9% 前景，真抗锯齿） |
| 强边缘落在过渡带比例 | **0.000** | **0.310**（遮罩贴合真实轮廓） |
| 站姿资产 | `stand.png` 916×1216 / 1150 KB（位图） | `stand.svg` 矢量 / **389 KB** |
| 最高可用尺寸 | 2×（再放大就糊） | **任意尺寸**（3× 渲染 1368×1809 依然后 525 KB 且锐利） |
| 矢量还原度 | — | 不透明区 IoU **0.9586**，SSIM 0.858，感知哈希距离 4 |

坐姿三层**没有**换成矢量：实测 `sit-body.svg` 反而更大（1152 KB vs 823 KB），
两条腿的矢量版形状失真（IoU 0.50 / 0.69，小目标易被样条拟合改变轮廓），
所以坐姿保留位图——指标不达标就不换，这是刻意决定。

### 新增的两个坑

8. **vtracer 的 SVG 常常没有 `viewBox`**：只改 `width`/`height` 时内容不会缩放，
   只会画到画布一角（表现为渲染后不透明区仅 25%，恰好等于面积比）。
   光栅化前若缺 `viewBox` 必须按原始尺寸补一个。
9. **不能用「删掉白色层」来给 SVG 做透明底**：角色自身的白发白衣也是白色，
   cutout 模式下背景层排序还不固定。正确做法是铺一个画里不存在的键控色（品红），
   矢量化后按颜色删除该色层（实测删 7 层，不透明区 71.4% vs 源 72.5%，IoU 0.9586）。

### A/B 验证的一个教训

宠物是持续呼吸/摆动的，两次抓帧本来就不同：实测**同一版本抓两次 SSIM 仅 0.339**。
所以「换资产前后抓帧比对」不能直接下结论，必须先做同版本对照实验定标噪声基底
（本案例中换资产带来的差异 0.3390 与噪声 0.3391 一致 → 说明资产切换无副作用）。