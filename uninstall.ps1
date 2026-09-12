<#
.SYNOPSIS
  把 Manim 可视化解释插件从这台 DSH 上摘干净。

.DESCRIPTION
  与 install.ps1 对称：调用 tools\dsh_installer.py 精确还原 cordis.patch.yml 与
  package.json，删除插件目录、Skill 副本与 node_modules 链接。

  默认**保留**已经渲染出的动画——它们是用户的产物，不该被卸载脚本删掉。

.EXAMPLE
  .\uninstall.ps1
  .\uninstall.ps1 -DryRun
  .\uninstall.ps1 -PurgeRenders      # 连 renders\ 一起删
#>
[CmdletBinding()]
param(
    [switch] $DryRun,
    [switch] $PurgeRenders,
    [string] $ProfileRoot = (Join-Path $HOME ".dsh\profiles\web"),
    [string] $PluginRoot  = (Join-Path $HOME ".dsh\plugins"),
    [string] $SkillRoot   = (Join-Path $HOME ".dsh\skills"),
    [string] $RenderRoot  = (Join-Path $PSScriptRoot "renders")
)

$ErrorActionPreference = "Stop"
$repo = $PSScriptRoot
$installer = Join-Path $repo "tools\dsh_installer.py"

if (-not (Test-Path $installer)) {
    throw "找不到安装器核心：$installer"
}

$python = (Get-Command "python" -ErrorAction SilentlyContinue).Source
if (-not $python) { throw "找不到 python。" }

Write-Host "Manim 可视化解释插件 — 卸载" -ForegroundColor Cyan

$arguments = @(
    $installer, "uninstall",
    "--profile-root", $ProfileRoot,
    "--plugin-root",  $PluginRoot,
    "--skill-root",   $SkillRoot,
    "--source-root",  $repo,
    "--render-root",  $RenderRoot,
    "--python",       $python
)
if ($DryRun)       { $arguments += "--dry-run" }
if ($PurgeRenders) { $arguments += "--purge-renders" }

& $python @arguments
if ($LASTEXITCODE -ne 0) { throw "安装器退出码 $LASTEXITCODE" }

if ($DryRun) {
    Write-Host "`n以上是 dry-run：没有写入任何文件。" -ForegroundColor Yellow
} else {
    Write-Host "`n已卸载。渲染产物目录已保留（要一并删除请加 -PurgeRenders）。" -ForegroundColor Green
    Write-Host "重启 dsh web 后左侧栏的「动画库」图标会消失。"
}
