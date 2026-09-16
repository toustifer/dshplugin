#!/usr/bin/env bash
# ==============================================================================
# Linux / macOS 卸载脚本
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALLER="${SCRIPT_DIR}/tools/dsh_installer.py"

DSH_DIR="${DSH_HOME:-${HOME}/.dsh}"
PROFILE_ROOT="${DSH_DIR}/profiles/web"
PLUGIN_ROOT="${DSH_DIR}/plugins"
SKILL_ROOT="${DSH_DIR}/skills"
RENDER_ROOT="${SCRIPT_DIR}/renders"
DRY_RUN=""
PURGE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run|-n)
            DRY_RUN="--dry-run"
            shift
            ;;
        --purge-renders)
            PURGE="--purge-renders"
            shift
            ;;
        *)
            shift
            ;;
    esac
done

PYTHON_BIN="$(which python3 || which python || true)"
if [[ -z "${PYTHON_BIN}" ]]; then
    echo "错误：未找到 python3。" >&2
    exit 1
fi

ARGS=(
    "${INSTALLER}" "uninstall"
    "--profile-root" "${PROFILE_ROOT}"
    "--plugin-root"  "${PLUGIN_ROOT}"
    "--skill-root"   "${SKILL_ROOT}"
    "--source-root"  "${SCRIPT_DIR}"
    "--render-root"  "${RENDER_ROOT}"
    "--python"       "${PYTHON_BIN}"
)

if [[ -n "${DRY_RUN}" ]]; then
    ARGS+=("${DRY_RUN}")
fi
if [[ -n "${PURGE}" ]]; then
    ARGS+=("${PURGE}")
fi

"${PYTHON_BIN}" "${ARGS[@]}"
