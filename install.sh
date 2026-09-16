#!/usr/bin/env bash
# ==============================================================================
# Linux / macOS 安装脚本 (兼容 POSIX bash / zsh)
# 职责：检测 Python3 / Manim / ffmpeg / LaTeX 等依赖，调用 tools/dsh_installer.py
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALLER="${SCRIPT_DIR}/tools/dsh_installer.py"

if [[ ! -f "${INSTALLER}" ]]; then
    echo "错误：找不到安装器核心脚本：${INSTALLER}" >&2
    exit 1
fi

DSH_DIR="${DSH_HOME:-${HOME}/.dsh}"
PROFILE_ROOT="${DSH_DIR}/profiles/web"
PLUGIN_ROOT="${DSH_DIR}/plugins"
SKILL_ROOT="${DSH_DIR}/skills"
RENDER_ROOT="${SCRIPT_DIR}/renders"
DRY_RUN=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run|-n)
            DRY_RUN="--dry-run"
            shift
            ;;
        --profile-root)
            PROFILE_ROOT="$2"
            shift 2
            ;;
        --plugin-root)
            PLUGIN_ROOT="$2"
            shift 2
            ;;
        --render-root)
            RENDER_ROOT="$2"
            shift 2
            ;;
        *)
            echo "未知参数: $1" >&2
            exit 1
            ;;
    esac
done

echo -e "\033[36mManim 可视化解释插件 — 安装 (POSIX / Linux / macOS)\033[0m"

# 1. 查找 Python 3
PYTHON_BIN="$(which python3 || which python || true)"
if [[ -z "${PYTHON_BIN}" ]]; then
    echo "错误：未找到 python3。请先安装 Python 3.11+。" >&2
    exit 1
fi

# 2. 检查依赖与可选工具
MANIM_BIN="$(which manim || true)"
FFMPEG_BIN="$(which ffmpeg || true)"
LATEX_BIN="$(which latex || true)"

if [[ -z "${MANIM_BIN}" ]]; then
    echo -e "\033[33m警告：PATH 上未检测到 manim。运行时将退回 'python -m manim'。\033[0m"
fi
if [[ -z "${FFMPEG_BIN}" ]]; then
    echo -e "\033[33m警告：PATH 上未检测到 ffmpeg。GIF 动图预览将无法生成。\033[0m"
fi
if [[ -z "${LATEX_BIN}" ]]; then
    echo -e "\033[33m警告：PATH 上未检测到 latex。MathTex 公式推导可能报错。\033[0m"
fi

ARGS=(
    "${INSTALLER}" "install"
    "--profile-root" "${PROFILE_ROOT}"
    "--plugin-root"  "${PLUGIN_ROOT}"
    "--skill-root"   "${SKILL_ROOT}"
    "--source-root"  "${SCRIPT_DIR}"
    "--render-root"  "${RENDER_ROOT}"
    "--python"       "${PYTHON_BIN}"
)

if [[ -n "${MANIM_BIN}" ]]; then
    ARGS+=("--manim" "${MANIM_BIN}")
fi
if [[ -n "${FFMPEG_BIN}" ]]; then
    ARGS+=("--ffmpeg" "${FFMPEG_BIN}")
fi
if [[ -n "${DRY_RUN}" ]]; then
    ARGS+=("${DRY_RUN}")
fi

"${PYTHON_BIN}" "${ARGS[@]}"

if [[ -n "${DRY_RUN}" ]]; then
    echo -e "\n\033[33m以上是 dry-run：未对系统做任何实际更改。\033[0m"
else
    echo -e "\n\033[32m安装完成！必须重启 DSH Web 实例才能使插件与前端生效。\033[0m"
fi
