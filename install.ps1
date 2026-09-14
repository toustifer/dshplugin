<#
.SYNOPSIS
  把 Manim 可视化解释插件挂到这台 DSH 上。

.DESCRIPTION
  依赖体检 → 调用 tools\dsh_installer.py 做真正的挂载 → 打印结果与重启提示。

  所有会改文件的逻辑都在那个 Python 模块里，因为它可以被 pytest 精确断言；
  这个脚本只做参数解析、依赖体检和转述，自己不解析也不写任何配置文件。

.EXAMPLE
  .\install.ps1
  .\install.ps1 -DryRun          # 只打印将要做的改动，不写任何文件

.EXAMPLE
  # 装到别处（测试或另一套 profile）
  .\install.ps1 -ProfileRoot C:\tmp\profile -RenderRoot C:\tmp\renders
#>
[CmdletBinding()]
param(
    [switch] $DryRun,
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

function Resolve-Tool([string] $Name) {
    $found = Get-Command $Name -ErrorAction SilentlyContinue
    if ($found) { return $found.Source }
    return $null
}

Write-Host "Manim 可视化解释插件 — 安装" -ForegroundColor Cyan

$python = Resolve-Tool "python"
if (-not $python) { throw "找不到 python。安装 Python 3.11+ 并确保它在 PATH 上。" }

$manim = Resolve-Tool "manim"
$ffmpeg = Resolve-Tool "ffmpeg"
$latex = Resolve-Tool "latex"

if (-not $manim)  { Write-Warning "PATH 上没有 manim。安装器会退回 'python -m manim'，请确认 manim 可被该解释器导入。" }
if (-not $ffmpeg) { Write-Warning "PATH 上没有 ffmpeg。GIF 预览无法生成（MP4 不受影响）。" }
if (-not $latex)  { Write-Warning "PATH 上没有 latex。公式（MathTex）会渲染失败。" }

$arguments = @(
    $installer, "install",
    "--profile-root", $ProfileRoot,
    "--plugin-root",  $PluginRoot,
    "--skill-root",   $SkillRoot,
    "--source-root",  $repo,
    "--render-root",  $RenderRoot,
    "--python",       $python
)
if ($manim)  { $arguments += @("--manim",  $manim) }
if ($ffmpeg) { $arguments += @("--ffmpeg", $ffmpeg) }
if ($DryRun) { $arguments += "--dry-run" }

& $python @arguments
if ($LASTEXITCODE -ne 0) { throw "安装器退出码 $LASTEXITCODE" }

if ($DryRun) {
    Write-Host "`n以上是 dry-run：没有写入任何文件。" -ForegroundColor Yellow
} else {
    Write-Host "`n安装完成。**必须重启 dsh web 才会生效**：" -ForegroundColor Green
    Write-Host "  & `"$HOME\.dsh\restart-web.ps1`""
    Write-Host "重启后应能看到："
    Write-Host "  1. 会话头部右上角「动画库」图标（右侧展开，不占全屏）；"
    Write-Host "  2. 工具列表增加 mcp__media__publish_file，支持在对话里内嵌视频、音频、PDF首页预览及各种文件；"
    Write-Host "  3. 问一个值得画的问题，正文会内嵌 Manim 动画。"
}
