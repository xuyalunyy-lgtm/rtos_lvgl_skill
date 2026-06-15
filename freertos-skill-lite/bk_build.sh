#!/usr/bin/env bash
# bk_build.sh — BK (Beken Armino) 编译/清理脚本
#
# 放置位置：与 SDK 同级目录，例如：
#   ~/armino/
#   ├── bk_avdk_smp/          ← SDK
#   ├── bk_solution_ai/       ← 可选方案仓
#   ├── my_firmware/          ← 可选自定义工程
#   └── bk_build.sh           ← 本脚本
#
# 用法：
#   ./bk_build.sh build                  # 编译（自动探测 SDK / 工程）
#   ./bk_build.sh clean                  # 清理
#   ./bk_build.sh rebuild                # 清理后编译
#   ./bk_build.sh build -p bk_solution_ai/projects/beken_genie
#   ./bk_build.sh build -s bk7258 -p lvgl/widgets    # SDK 内 Demo 工程
#
# 环境变量（可选，写入 bk_build.env 自动加载）：
#   BK_SDK_DIR      SDK 根目录（含 Makefile）
#   BK_PROJECT_DIR  工程目录（含 Makefile；方案仓工程）
#   BK_SOC          芯片目标，默认 bk7258
#   BK_PROJECT      SDK 内工程相对路径，如 lvgl/widgets（与 BK_PROJECT_DIR 二选一）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOC_DEFAULT="bk7258"

# 加载同级配置文件
if [[ -f "${SCRIPT_DIR}/bk_build.env" ]]; then
    # shellcheck disable=SC1091
    source "${SCRIPT_DIR}/bk_build.env"
fi

BK_SDK_DIR="${BK_SDK_DIR:-}"
BK_PROJECT_DIR="${BK_PROJECT_DIR:-}"
BK_SOC="${BK_SOC:-$SOC_DEFAULT}"
BK_PROJECT="${BK_PROJECT:-}"

ACTION=""
USER_PROJECT=""
USER_SOC=""

usage() {
    cat <<'EOF'
用法: bk_build.sh <build|clean|rebuild> [选项]

选项:
  -p, --project <path>   工程路径（相对脚本目录或绝对路径）
                         - SDK 内 Demo: lvgl/widgets
                         - 方案仓工程: bk_solution_ai/projects/beken_genie
  -s, --soc <soc>        芯片目标，默认 bk7258
  -h, --help             帮助

示例:
  ./bk_build.sh build -p bk_solution_ai/projects/beken_genie
  ./bk_build.sh clean  -p lvgl/widgets
  ./bk_build.sh rebuild
EOF
}

log() { printf '[bk_build] %s\n' "$*"; }
die() { printf '[bk_build] 错误: %s\n' "$*" >&2; exit 1; }

resolve_path() {
    local p="$1"
    if [[ "$p" = /* ]]; then
        echo "$p"
    else
        echo "${SCRIPT_DIR}/${p}"
    fi
}

find_sdk_dir() {
    if [[ -n "$BK_SDK_DIR" && -f "${BK_SDK_DIR}/Makefile" ]]; then
        echo "$(resolve_path "$BK_SDK_DIR")"
        return
    fi
    local candidates=("bk_avdk_smp" "bk_avdk" "armino/bk_avdk_smp" "armino/bk_avdk")
    local c abs
    for c in "${candidates[@]}"; do
        abs="$(resolve_path "$c")"
        if [[ -f "${abs}/Makefile" ]]; then
            echo "$abs"
            return
        fi
    done
    die "未找到 SDK。请设置 BK_SDK_DIR 或将 bk_avdk_smp 放在与脚本同级目录。"
}

# 判断 path 是否为 SDK 内 projects/ 下工程（返回相对 PROJECT= 路径）
sdk_internal_project_rel() {
    local proj_abs="$1"
    local sdk_abs="$2"
    local rel="${proj_abs#"${sdk_abs}/"}"
    if [[ "$rel" == projects/* ]]; then
        echo "${rel#projects/}"
        return 0
    fi
    return 1
}

detect_project() {
    local sdk="$1"
    local proj=""

    if [[ -n "$USER_PROJECT" ]]; then
        proj="$(resolve_path "$USER_PROJECT")"
    elif [[ -n "$BK_PROJECT_DIR" ]]; then
        proj="$(resolve_path "$BK_PROJECT_DIR")"
    elif [[ -n "$BK_PROJECT" ]]; then
        echo "SDK_INTERNAL:${BK_PROJECT}"
        return
    elif [[ -f "${PWD}/Makefile" ]]; then
        proj="$PWD"
    fi

    if [[ -z "$proj" ]]; then
        die "未指定工程。使用 -p <path> 或设置 BK_PROJECT_DIR / BK_PROJECT，或在工程目录内执行。"
    fi

    if [[ ! -f "${proj}/Makefile" ]]; then
        die "工程目录无 Makefile: ${proj}"
    fi

    if internal_rel="$(sdk_internal_project_rel "$proj" "$sdk" 2>/dev/null)"; then
        echo "SDK_INTERNAL:${internal_rel}"
    else
        echo "EXTERNAL:${proj}"
    fi
}

run_make() {
    local target_cmd="$1"   # build | clean
    local sdk="$2"
    local mode="$3"         # SDK_INTERNAL:xxx | EXTERNAL:path
    local soc="$4"

    if [[ "$mode" == SDK_INTERNAL:* ]]; then
        local proj_rel="${mode#SDK_INTERNAL:}"
        log "模式: SDK 内工程"
        log "SDK_DIR=${sdk}"
        log "PROJECT=${proj_rel}"
        log "SOC=${soc}"
        (
            cd "$sdk"
            if [[ "$target_cmd" == "clean" ]]; then
                make clean "${soc}" "PROJECT=${proj_rel}"
            else
                make "${soc}" "PROJECT=${proj_rel}"
            fi
        )
    else
        local proj_dir="${mode#EXTERNAL:}"
        log "模式: 方案仓 / 外部工程"
        log "SDK_DIR=${sdk}"
        log "PROJECT_DIR=${proj_dir}"
        log "SOC=${soc}"
        (
            cd "$proj_dir"
            export SDK_DIR="$sdk"
            if [[ "$target_cmd" == "clean" ]]; then
                make clean "${soc}"
            else
                make "${soc}"
            fi
        )
    fi
}

print_artifact_hint() {
    local sdk="$1"
    local mode="$2"
    local soc="$3"
    log "编译完成。固件路径请查看工程 build/ 目录，常见："
    if [[ "$mode" == EXTERNAL:* ]]; then
        local proj_dir="${mode#EXTERNAL:}"
        log "  ${proj_dir}/build/${soc}/*/package/all-app.bin"
    else
        local proj_rel="${mode#SDK_INTERNAL:}"
        log "  ${sdk}/build/${soc}/${proj_rel//\//_}/package/  (依 SDK 版本可能略有差异)"
    fi
}

# ── 参数解析 ─────────────────────────────────────────────
if [[ $# -lt 1 ]]; then
    usage
    exit 1
fi

ACTION="$1"
shift

while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--project) USER_PROJECT="$2"; shift 2 ;;
        -s|--soc)     USER_SOC="$2"; shift 2 ;;
        -h|--help)    usage; exit 0 ;;
        *) die "未知参数: $1" ;;
    esac
done

case "$ACTION" in
    build|clean|rebuild) ;;
    *) die "未知动作: ${ACTION}（支持 build / clean / rebuild）" ;;
esac

SOC="${USER_SOC:-$BK_SOC}"
SDK_DIR="$(find_sdk_dir)"
PROJECT_MODE="$(detect_project "$SDK_DIR")"

do_clean() { run_make clean "$SDK_DIR" "$PROJECT_MODE" "$SOC"; }
do_build() {
    run_make build "$SDK_DIR" "$PROJECT_MODE" "$SOC"
    print_artifact_hint "$SDK_DIR" "$PROJECT_MODE" "$SOC"
}

case "$ACTION" in
    clean)   do_clean ;;
    build)   do_build ;;
    rebuild) do_clean; do_build ;;
esac

log "完成: ${ACTION}"
