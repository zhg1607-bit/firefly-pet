# deploy_silver_pet.ps1 —— 把 dist\webm 的成品部署到「银白少女」文件宠物（只碰它自己的目录，绝不碰 main-animation）
# 用法：pwsh -File tools\deploy_silver_pet.ps1 [-SkipBackup]
param([switch]$SkipBackup)

$ErrorActionPreference = 'Stop'
$root   = Split-Path -Parent $PSScriptRoot
$pet    = Join-Path $env:USERPROFILE '.dsh\dsh-pet'
$animDir= Join-Path $pet 'pet\银白少女-animation'
$cfgSrc = Join-Path $root 'pet-config\银白少女-config.jsonc'
$cfgDst = Join-Path $pet 'pet\银白少女-config.jsonc'
$dist   = Join-Path $root 'dist\webm'
$backup = Join-Path $root 'work\backup\pet'

Write-Output "动画来源 : $dist"
Write-Output "动画目标 : $animDir"

if (-not (Test-Path $dist)) { Write-Error "dist\webm 不存在，先跑 run_pipeline.ps1"; exit 1 }
New-Item -ItemType Directory -Force -Path $animDir | Out-Null

$files = Get-ChildItem "$dist\*.webm" -File
if ($files.Count -eq 0) { Write-Error "dist\webm 里没有 webm"; exit 1 }
Write-Output "部署 $($files.Count) 个 webm ..."

# 备份旧的（避免覆盖丢失）
if (-not $SkipBackup) {
  New-Item -ItemType Directory -Force -Path $backup | Out-Null
  $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  foreach ($f in (Get-ChildItem "$animDir\*.webm" -File -ErrorAction SilentlyContinue)) {
    Copy-Item -Force $f.FullName (Join-Path $backup ($f.Name + '.' + $stamp))
  }
  Write-Output "已备份旧动画 -> $backup"
}

foreach ($f in $files) {
  Copy-Item -Force $f.FullName (Join-Path $animDir $f.Name)
}
Write-Output "动画部署完成，共 $($files.Count) 个。"

# 配置
if (Test-Path $cfgSrc) {
  Copy-Item -Force $cfgSrc $cfgDst
  Write-Output "配置已部署 -> $cfgDst"
} else {
  Write-Warning "缺配置 $cfgSrc，动画已就位但配置未更新"
}

Write-Output "--- 银白少女-animation 现状 ---"
Get-ChildItem $animDir -File | Sort-Object Name | Select-Object Name,Length | Format-Table -AutoSize
Write-Output "完成。到页面 Ctrl+F5 刷新即可。"
