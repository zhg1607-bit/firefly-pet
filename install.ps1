<#
  银白少女 · 桌宠素材包 一键安装
  ---------------------------------------------------------------
  用法（在本文件所在目录打开 PowerShell）：
      powershell -ExecutionPolicy Bypass -File .\install.ps1
  或直接双击 install.cmd
  可选参数：
      -PetRoot <路径>    自定义 DSH 桌宠目录（默认 %USERPROFILE%\.dsh\dsh-pet）
      -DryRun            只打印将要做的事，不写盘
  ---------------------------------------------------------------
  安装内容：
      dist\webm\*.webm                  -> <PetRoot>\pet\银白少女-animation\
      memes\*.png                       -> <PetRoot>\pet\银白少女-memes\
      pet-config\银白少女-config.jsonc  -> <PetRoot>\pet\银白少女-config.jsonc
  已有旧文件会先备份到 <PetRoot>\pet\_backup-银白少女-<时间戳>\
#>
[CmdletBinding()]
param(
    [string]$PetRoot = (Join-Path $env:USERPROFILE '.dsh\dsh-pet'),
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$id   = '银白少女'
$here = $PSScriptRoot
$pet  = Join-Path $PetRoot 'pet'

$srcAnim  = Join-Path $here 'dist\webm'
$srcMemes = Join-Path $here 'memes'
$srcCfg   = Join-Path $here ('pet-config\{0}-config.jsonc' -f $id)

$dstAnim  = Join-Path $pet ('{0}-animation' -f $id)
$dstMemes = Join-Path $pet ('{0}-memes'     -f $id)
$dstCfg   = Join-Path $pet ('{0}-config.jsonc' -f $id)

function Say($m, $c = 'Gray') { Write-Host $m -ForegroundColor $c }

Say '==============================================' Cyan
Say ' 银白少女 · 桌宠素材包 一键安装' Cyan
Say '==============================================' Cyan
Say ('来源目录 : {0}' -f $here)
Say ('目标目录 : {0}' -f $PetRoot)
Say ('模式     : {0}' -f $(if ($DryRun) { '试运行（不写盘）' } else { '正式安装' }))
Say ''

Say '[1/4] 检查来源文件' Yellow
$webms = @(); $memes = @()
if (Test-Path $srcAnim)  { $webms = @(Get-ChildItem $srcAnim  -Filter *.webm -File) }
if (Test-Path $srcMemes) { $memes = @(Get-ChildItem $srcMemes -Filter *.png  -File) }
Say ('  dist\webm\*.webm                  {0} 个' -f $webms.Count)
Say ('  memes\*.png                       {0} 个' -f $memes.Count)
Say ('  pet-config\{0}-config.jsonc   {1}' -f $id, $(if (Test-Path $srcCfg) { '有' } else { '缺失' }))
if ($webms.Count -eq 0)       { Say '  x 没找到动画文件，安装中止。' Red; exit 1 }
if (-not (Test-Path $srcCfg)) { Say '  x 没找到配置文件，安装中止。' Red; exit 1 }

Say ''
Say '[2/4] 检查目标环境' Yellow
if (Test-Path $PetRoot) {
    Say '  v 找到 DSH 桌宠目录'
} else {
    Say ('  ! 没找到 {0}' -f $PetRoot) DarkYellow
    Say '    这台机器可能还没装 dsh-pet 桌宠插件（见 README 第 0 步）；' DarkYellow
    Say '    素材照常放入，装好插件后即可生效。' DarkYellow
}

if ($DryRun) {
    Say ''
    Say '试运行结束，什么都没改。去掉 -DryRun 即正式安装。' Green
    exit 0
}

Say ''
Say '[3/4] 备份旧文件' Yellow
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$bak = Join-Path $pet ('_backup-{0}-{1}' -f $id, $stamp)
$hadOld = $false
if (Test-Path $dstCfg)   { $hadOld = $true }
if (Test-Path $dstAnim)  { if (@(Get-ChildItem $dstAnim  -File -ErrorAction SilentlyContinue).Count -gt 0) { $hadOld = $true } }
if (Test-Path $dstMemes) { if (@(Get-ChildItem $dstMemes -File -ErrorAction SilentlyContinue).Count -gt 0) { $hadOld = $true } }
if ($hadOld) {
    New-Item -ItemType Directory -Force -Path $bak | Out-Null
    if (Test-Path $dstCfg)   { Copy-Item $dstCfg $bak -Force }
    if (Test-Path $dstAnim)  { Copy-Item $dstAnim  $bak -Recurse -Force }
    if (Test-Path $dstMemes) { Copy-Item $dstMemes $bak -Recurse -Force }
    Say ('  v 已备份 {0} 个旧文件 -> {1}' -f @(Get-ChildItem $bak -Recurse -File).Count, $bak) Green
} else {
    Say '  - 没有旧文件，跳过备份'
}

Say ''
Say '[4/4] 拷贝素材' Yellow
New-Item -ItemType Directory -Force -Path $dstAnim, $dstMemes | Out-Null
Copy-Item (Join-Path $srcAnim '*') $dstAnim -Force
if ($memes.Count -gt 0) { Copy-Item (Join-Path $srcMemes '*') $dstMemes -Force }
Copy-Item $srcCfg $dstCfg -Force
Say ('  v 动画 {0} 条 -> {1}' -f @(Get-ChildItem $dstAnim  -Filter *.webm -File).Count, $dstAnim) Green
Say ('  v 表情包 {0} 张 -> {1}' -f @(Get-ChildItem $dstMemes -Filter *.png  -File).Count, $dstMemes) Green
Say ('  v 配置     -> {0}' -f $dstCfg) Green
Say ''
Say '安装完成！回到 DSH 桌面端按 Ctrl+F5 刷新，就能看到「银白少女」。' Green
Say ''
Say '卸载：删掉上面列出的两个目录 + 配置文件即可（旧文件在 _backup-* 里有备份，可原样还原）。'