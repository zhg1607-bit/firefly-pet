#Requires -Version 5.1
<#
.SYNOPSIS
    桌面宠物素材链一键脚本：绿幕 mp4 -> 透明 webm（VP9-alpha）。

.DESCRIPTION
    依次执行（每一步都有「已完成就跳过」的断点续跑）：

        0. 生成水印蒙版   video/watermark_mask_v5.mkv   （仅当缺蒙版且给了纯黑参考视频）
        1. 去水印         video/*.mp4       -> step01/*.mp4
        2. 绿幕抠像       step01/*.mp4      -> step02/*.webm   （VP9-alpha）
        3. 画布归一化     step02/*.webm     -> step03/*.webm   （2160x1215、角色高 900、脚底 1115）
        4. 缩略图         step03/*.webm     -> step04/*.webm   （640x360，插件实际播放的格式）
        5. alpha 校验     step04/*.webm
        6. 汇总到 dist/   dist/webm/*.webm（-Deploy 时直接拷进插件的用户素材目录）

.PARAMETER Python
    python.exe 路径。不给就自动探测：PATH 上的 python / py，再退回 DSH 内置运行时。

.PARAMETER SkipWatermark
    跳过第 0、1 步（源视频本身没有水印时用，例如用剪映/PR 自己导出、或视频工具已去水印）。

.PARAMETER BlackVideo
    纯黑参考视频路径（与源视频同一个水印）。默认 work/black_10s.mp4。

.PARAMETER Clean
    先清空 step01~step04 与 dist，再从头跑。

.PARAMETER NoDist
    不往 dist/ 汇总。

.PARAMETER Deploy
    把 step04 的 webm 拷到 %DSH_HOME%\dsh-pet\main-animation\webm\（插件的用户素材目录，
    优先于包内素材；文件名 = 插件内置动画名即可零配置替换）。等价于手动复制。

.EXAMPLE
    pwsh -File run_pipeline.ps1
    pwsh -File run_pipeline.ps1 -Clean -Deploy
    pwsh -File run_pipeline.ps1 -SkipWatermark
#>
[CmdletBinding()]
param(
    [string]$Python = '',
    [switch]$SkipWatermark,
    [string]$BlackVideo = '',
    [switch]$Clean,
    [switch]$NoDist,
    [switch]$Deploy
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}

$ROOT  = $PSScriptRoot
$TOOLS = Join-Path $ROOT '.tools\ffmpeg-9.0.1-essentials_build\bin'
$FFMPEG  = Join-Path $TOOLS 'ffmpeg.exe'
$FFPROBE = Join-Path $TOOLS 'ffprobe.exe'
$SCRIPTS = Join-Path $ROOT 'scripts'
$VIDEO   = Join-Path $ROOT 'video'
$WORK    = Join-Path $ROOT 'work'
$DIST    = Join-Path $ROOT 'dist'
$MASK    = Join-Path $VIDEO 'watermark_mask_v5.mkv'

$script:Failed = @()

function Say([string]$msg, [string]$color = 'Gray') {
    Write-Host $msg -ForegroundColor $color
}

function Section([string]$title) {
    Write-Host ''
    Write-Host ('=' * 68) -ForegroundColor DarkCyan
    Write-Host "  $title" -ForegroundColor Cyan
    Write-Host ('=' * 68) -ForegroundColor DarkCyan
}

function Invoke-Step([string]$title, [string]$scriptName, [string[]]$extraArgs = @()) {
    Section $title
    $path = Join-Path $SCRIPTS $scriptName
    if (-not (Test-Path $path)) {
        Say "找不到脚本: $path" 'Red'
        $script:Failed += $title
        return $false
    }
    $cmdArgs = @($path) + $extraArgs
    & $Python @cmdArgs
    if ($LASTEXITCODE -ne 0) {
        Say "[失败] $title （退出码 $LASTEXITCODE）" 'Red'
        $script:Failed += $title
        return $false
    }
    return $true
}

# ---------------------------------------------------------------- 环境自检
Section '环境自检'

if (-not (Test-Path $FFMPEG)) {
    Say "缺少 ffmpeg: $FFMPEG" 'Red'
    Say '请把 ffmpeg 解压到 .tools\ffmpeg-9.0.1-essentials_build\ （脚本按这个固定路径找它）' 'Yellow'
    exit 1
}

if (-not $Python) {
    # 候选顺序：DSH 内置运行时优先（numpy/scipy/Pillow 齐备），再找 PATH 上的 python / py。
    # 注意 Windows 自带一个 Microsoft\WindowsApps\python.exe 占位符（跑起来只会弹应用商店、
    # 退出码 9009），所以每个候选都必须真跑一次依赖自检，通过才算数。
    $cands = New-Object System.Collections.ArrayList
    if ($env:DSH_HOME) {
        [void]$cands.Add((Join-Path $env:DSH_HOME 'dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'))
    }
    [void]$cands.Add((Join-Path $env:USERPROFILE '.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'))
    foreach ($name in @('python', 'python3', 'py')) {
        $c = Get-Command $name -ErrorAction SilentlyContinue
        if ($c) { [void]$cands.Add($c.Source) }
    }
    foreach ($cand in $cands) {
        if (-not $cand -or -not (Test-Path $cand)) { continue }
        $probe = & $cand -c "import sys,numpy,scipy,PIL;print(sys.version.split()[0])" 2>$null
        if ($LASTEXITCODE -eq 0 -and $probe) {
            $Python = $cand
            Say ("python 自检通过（{0}，numpy/scipy/Pillow 齐备）" -f $probe) 'DarkGray'
            break
        }
        Say "跳过不可用的 python 候选：$cand" 'DarkGray'
    }
}
if (-not $Python -or -not (Test-Path $Python)) {
    Say '找不到可用的 python.exe（需要 numpy + scipy + Pillow），请用 -Python 指定路径。' 'Red'
    Say '例：-Python "$env:DSH_HOME\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"' 'Yellow'
    exit 1
}
Say "工程根目录 : $ROOT"
Say "python     : $Python"
Say ("ffmpeg     : " + (& $FFMPEG -version | Select-Object -First 1))

foreach ($d in 'video', 'work', 'step01', 'step02', 'step03', 'step04') {
    New-Item -ItemType Directory -Force -Path (Join-Path $ROOT $d) | Out-Null
}

if ($Clean) {
    Section '清空中间产物'
    foreach ($d in 'step01', 'step02', 'step03', 'step04', 'dist') {
        $p = Join-Path $ROOT $d
        if (Test-Path $p) { Remove-Item $p -Recurse -Force; Say "已删除 $d\" 'Yellow' }
    }
    foreach ($d in 'step01', 'step02', 'step03', 'step04') {
        New-Item -ItemType Directory -Force -Path (Join-Path $ROOT $d) | Out-Null
    }
}

# ------------------------------------------------------- 0. 水印蒙版 / 源视频盘点
Section '源视频盘点'
$sources = @(Get-ChildItem -Path $VIDEO -Filter '*.mp4' -File -ErrorAction SilentlyContinue)
if ($sources.Count -eq 0) {
    Say "video\ 里没有 *.mp4 —— 请先把 AI 视频工具生成的 10 秒绿幕视频放进去。" 'Yellow'
    Say '（提示词见 prompts\actions\ 下的单动作文件，或 prompts\action-10s.md）' 'Yellow'
    exit 1
}
Say ("发现 {0} 个源视频：" -f $sources.Count)
$sources | ForEach-Object { Say ("  - {0}  ({1:N1} MB)" -f $_.Name, ($_.Length / 1MB)) }

if (-not $SkipWatermark) {
    if (-not $BlackVideo) { $BlackVideo = Join-Path $WORK 'black_10s.mp4' }
    if (-not (Test-Path $MASK)) {
        if (Test-Path $BlackVideo) {
            Section '生成水印蒙版（由纯黑参考视频）'
            & $Python (Join-Path $SCRIPTS 'make_mask_black.py') $BlackVideo $MASK 20
            if ($LASTEXITCODE -ne 0) { Say '蒙版生成失败' 'Red'; $script:Failed += 'make_mask_black' }
        } else {
            Say "没有蒙版（$MASK），也没有纯黑参考视频（$BlackVideo）。" 'Yellow'
            Say '=> 自动跳过第 1 步「去水印」。' 'Yellow'
            Say '   要补的话：用同一个 AI 视频工具导出一段 10 秒纯黑视频（水印位置/大小必须一致），' 'Yellow'
            Say '   存成 work\black_10s.mp4，再跑 python scripts\make_mask_black.py' 'Yellow'
            $SkipWatermark = $true
        }
    } else {
        Say "已有蒙版，跳过生成：$MASK" 'DarkGray'
    }
}

# ------------------------------------------------------------------ 主流程
if (-not $SkipWatermark) {
    Invoke-Step '① 去水印  video/*.mp4 -> step01/*.mp4' 'watermark_step01.py' | Out-Null
} else {
    Section '① 去水印（已跳过）'
    Say '把 video\*.mp4 原样复制到 step01\，让后面的抠像步骤有输入。' 'Yellow'
    foreach ($f in $sources) {
        $dst = Join-Path $ROOT ('step01\' + $f.Name)
        if (-not (Test-Path $dst) -or (Get-Item $dst).LastWriteTime -lt $f.LastWriteTime) {
            Copy-Item $f.FullName $dst -Force
            Say "  已复制 $($f.Name)" 'DarkGray'
        }
    }
}

Invoke-Step '② 绿幕抠像  step01/*.mp4 -> step02/*.webm' 'chroma_step02.py' | Out-Null
Invoke-Step '③ 画布归一化  step02/*.webm -> step03/*.webm' 'normalize_step03.py' | Out-Null
Invoke-Step '④ 缩略图      step03/*.webm -> step04/*.webm' 'encode_thumbs.py' | Out-Null

# -------------------------------------------------------------- alpha 校验
Section '⑤ alpha 校验（step04）'
$finals = @(Get-ChildItem -Path (Join-Path $ROOT 'step04') -Filter '*.webm' -File -ErrorAction SilentlyContinue)
if ($finals.Count -gt 0) {
    & $Python (Join-Path $SCRIPTS 'check_alpha.py') @($finals | ForEach-Object { $_.FullName })
    if ($LASTEXITCODE -ne 0) { Say '有素材 alpha 校验没过，注意上面标了 !! LOST 的文件' 'Yellow' }
} else {
    Say 'step04 里没有产物' 'Red'
    $script:Failed += 'encode_thumbs'
}

# ------------------------------------------------------------------ 汇总
$finals = @(Get-ChildItem -Path (Join-Path $ROOT 'step04') -Filter '*.webm' -File -ErrorAction SilentlyContinue)

if (-not $NoDist -and $finals.Count -gt 0) {
    Section '⑥ 汇总到 dist\webm'
    $distWebm = Join-Path $DIST 'webm'
    New-Item -ItemType Directory -Force -Path $distWebm | Out-Null
    $finals | ForEach-Object { Copy-Item $_.FullName (Join-Path $distWebm $_.Name) -Force }
    Say ("已汇总 {0} 个 webm -> {1}" -f $finals.Count, $distWebm) 'Green'
}

if ($Deploy -and $finals.Count -gt 0) {
    Section '⑦ 部署到插件用户素材目录'
    $home_ = $env:DSH_HOME
    if (-not $home_) { $home_ = Join-Path $env:USERPROFILE '.dsh' }
    $target = Join-Path $home_ 'dsh-pet\main-animation\webm'
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    $n = 0
    foreach ($f in $finals) {
        Copy-Item $f.FullName (Join-Path $target $f.Name) -Force
        $n++
    }
    Say ("已部署 {0} 个 webm -> {1}" -f $n, $target) 'Green'
    Say '刷新 DSH 页面即可生效（文件名 = 插件内置动画名时零配置覆盖，见 prompts\动作名对照表.md）' 'Yellow'
}

# ------------------------------------------------------------------ 总结
Section '完成'
$steps = @(
    @{ n = 'step01 去水印';    d = 'step01' },
    @{ n = 'step02 抠像';      d = 'step02' },
    @{ n = 'step03 归一化';    d = 'step03' },
    @{ n = 'step04 缩略图';    d = 'step04' }
)
foreach ($s in $steps) {
    $items = @(Get-ChildItem -Path (Join-Path $ROOT $s.d) -File -ErrorAction SilentlyContinue |
               Where-Object { $_.Extension -in '.mp4', '.webm' })
    $mb = 0.0
    if ($items.Count -gt 0) { $mb = ($items | Measure-Object Length -Sum).Sum / 1MB }
    Say ("  {0,-14} {1,3} 个  {2,8:N1} MB" -f $s.n, $items.Count, $mb)
}
if ($script:Failed.Count -gt 0) {
    Say ''
    Say ('以下步骤失败：' + ($script:Failed -join '、')) 'Red'
    exit 1
}
Say ''
Say '全部完成。' 'Green'
if (-not $Deploy -and $finals.Count -gt 0) {
    Say '手动部署：把 step04\*.webm 复制到 %DSH_HOME%\dsh-pet\main-animation\webm\，刷新页面。' 'Yellow'
}
exit 0
