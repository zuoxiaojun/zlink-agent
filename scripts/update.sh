#!/usr/bin/env bash
# ===========================================================================
# scripts/update.sh — ZLink Agent 安全升级脚本
#
# 功能：
#   1. 自动备份 data/ 目录（保留最近 5 份）
#   2. git pull 拉取最新代码（data/ 在 .gitignore 中，不会被触碰）
#   3. 更新 Python 依赖
#   4. 更新前端依赖
#   5. 执行数据迁移（如有）
#   6. 输出升级结果
#
# 安全保证：
#   - 升级前自动全量备份 data/ → data/backups/ 目录
#   - data/ 目录被 .gitignore 排除，git pull 不会改动任何用户数据
#   - 本地未提交的修改通过 git stash 暂存，升级后恢复
#   - 所有操作均幂等，可重复执行
#
# 备份说明：
#   备份文件位于 data/backups/ 目录：
#     zlink-agent-data-2026-07-03_143000.tar.gz
#   保留最近 5 份备份，超出自动清理。
#   恢复方式：tar -xzf data/backups/<文件名> -C data/
#
# 用法：
#   bash scripts/update.sh          # 执行升级（含备份）
#   bash scripts/update.sh --check  # 仅检查是否有更新
# ===========================================================================

set -euo pipefail

# ── 颜色 ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()   { echo -e "${RED}[ERROR]${NC} $*"; }

# ── 项目根目录 ──────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# ── 版本信息 ────────────────────────────────────────────────────────────────
CURRENT_VERSION=$(git describe --tags --always 2>/dev/null || echo "unknown")
CURRENT_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# ── 仅检查模式 ──────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--check" ]]; then
    info "当前版本: $CURRENT_VERSION ($CURRENT_HASH)"
    git fetch --tags --quiet 2>/dev/null || true
    LATEST_HASH=$(git rev-parse --short @{upstream} 2>/dev/null || echo "unknown")
    LATEST_TAG=$(git describe --tags --always @{upstream} 2>/dev/null || echo "unknown")

    if [[ "$CURRENT_HASH" == "$LATEST_HASH" ]]; then
        ok "已是最新版本: $CURRENT_VERSION"
        echo "UPDATE_AVAILABLE=false"
        echo "CURRENT_VERSION=$CURRENT_VERSION"
    else
        info "发现新版本: $LATEST_TAG ($LATEST_HASH)"
        echo "UPDATE_AVAILABLE=true"
        echo "CURRENT_VERSION=$CURRENT_VERSION"
        echo "LATEST_VERSION=$LATEST_TAG"
    fi
    exit 0
fi

# ── 前置检查 ────────────────────────────────────────────────────────────────
if ! git rev-parse --is-inside-work-tree &>/dev/null; then
    err "当前目录不是一个 git 仓库，无法更新。"
    err "请从 git clone 的原始项目目录运行此脚本。"
    exit 1
fi

if ! command -v pip &>/dev/null && ! command -v pip3 &>/dev/null; then
    err "未找到 pip/pip3，请先安装 Python。"
    exit 1
fi

PIP=$(command -v pip3 || command -v pip)

# ── 数据目录 ────────────────────────────────────────────────────────────────
# 运行时数据目录 ~/.zlink-agent/data/（config.json, sessions, memory 等）
DATA_DIR="${ZLINK_DATA_DIR:-$HOME/.zlink-agent/data}"
BACKUP_DIR="$DATA_DIR/backups"
BACKUP_RETENTION=5  # 保留最近 5 份备份

# ── 备份函数 ────────────────────────────────────────────────────────────────

do_backup() {
    mkdir -p "$BACKUP_DIR"

    local timestamp
    timestamp=$(date +%Y-%m-%d_%H%M%S)
    local backup_file="$BACKUP_DIR/zlink-agent-data-$timestamp.tar.gz"

    info "正在备份 data/ → $backup_file ..."

    # 用 tar 打包 DATA_DIR 下除 backups/ 自身以外的所有内容
    # --exclude 排除备份目录自身和日志（日志可丢弃）
    if tar -czf "$backup_file" \
        --exclude="backups" \
        --exclude="logs" \
        --exclude="yonsuite_cache" \
        -C "$(dirname "$DATA_DIR")" "$(basename "$DATA_DIR")" 2>/dev/null; then
        # 计算备份文件大小并显示
        local size
        size=$(du -h "$backup_file" | cut -f1)
        ok "备份完成 ($size) — $backup_file"
    else
        warn "备份过程中有非致命错误，请手动检查 data/ 完整性"
    fi
}

cleanup_old_backups() {
    # 保留最近 N 份，删除更旧的
    local count
    count=$(ls -1 "$BACKUP_DIR"/zlink-agent-data-*.tar.gz 2>/dev/null | wc -l)
    if [[ "$count" -gt "$BACKUP_RETENTION" ]]; then
        local to_delete
        to_delete=$(( count - BACKUP_RETENTION ))
        info "清理旧备份（保留 $BACKUP_RETENTION 份，删除 $to_delete 份）..."
        ls -1t "$BACKUP_DIR"/zlink-agent-data-*.tar.gz 2>/dev/null | tail -n "$to_delete" | while read -r old; do
            rm -f "$old"
            info "  已删除: $old"
        done
    fi
}

# ── 检查是否有更新 ──────────────────────────────────────────────────────────
info "正在检查更新..."
git fetch --quiet 2>/dev/null || warn "无法连接到远程仓库，将尝试本地 pull"

LATEST_HASH=$(git rev-parse --short @{upstream} 2>/dev/null || echo "")

REMOTE_URL=$(git remote get-url origin 2>/dev/null || echo "未知")

if [[ -n "$LATEST_HASH" && "$CURRENT_HASH" == "$LATEST_HASH" ]]; then
    ok "当前 ($CURRENT_VERSION) 已是最新版本，无需更新。"
    echo ""
    echo "── 版本信息 ──────────────────────────────"
    echo "  当前版本 : $CURRENT_VERSION"
    echo "  Commit   : $CURRENT_HASH"
    echo "  远端地址 : $REMOTE_URL"
    echo "  数据目录 : $DATA_DIR/"
    echo "──────────────────────────────────────────"
    exit 0
fi

echo ""
echo "═══════════════════════════════════════════"
echo "  版本: $CURRENT_VERSION → 最新"
echo "  Commit: $CURRENT_HASH → $LATEST_HASH"
echo "  远端: $REMOTE_URL"
echo "═══════════════════════════════════════════"
echo ""

# ── 备份当前版本信息（以防升级失败回滚用） ─────────────────────────────────
PREVIOUS_HASH="$CURRENT_HASH"

# ── 备份 data/ 用户数据 ─────────────────────────────────────────────────────
echo ""
info "━━━━ 第一步：数据备份 ━━━━"
do_backup
cleanup_old_backups
echo ""

# ── Stash 本地未提交更改 ────────────────────────────────────────────────────
if ! git diff --quiet 2>/dev/null; then
    info "暂存本地未提交的修改..."
    git stash --include-untracked -m "ZLink Agent auto-stash before update $(date +%Y%m%d_%H%M%S)" 2>/dev/null || true
    HAD_STASH=true
else
    HAD_STASH=false
fi

# ── 拉取最新代码 ────────────────────────────────────────────────────────────
info "正在拉取最新代码..."
if git pull --ff-only 2>/dev/null; then
    ok "代码拉取成功"
else
    # 如果 --ff-only 失败（有分叉），尝试 rebase
    warn "快速合并失败，尝试 rebase..."
    if git pull --rebase 2>/dev/null; then
        ok "代码拉取成功 (rebase)"
    else
        err "代码拉取失败，请手动处理冲突后重试。"
        err "冲突通常只发生在你修改了项目代码文件（非 data/ 目录）的情况下。"
        # 恢复 stash
        if $HAD_STASH; then
            git stash pop 2>/dev/null || true
        fi
        exit 1
    fi
fi

NEW_HASH=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
NEW_VERSION=$(git describe --tags --always 2>/dev/null || echo "unknown")

# ── 镜像回退 (与 setup.sh 一致) ─────────────────────────────────────────
USE_MIRROR="${ZLINK_USE_MIRROR:-true}"
NPM_MIRROR="${ZLINK_NPM_MIRROR:-https://mirrors.npmmirror.com}"
PIP_MIRRORS=(
    "https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple"
    "https://mirrors.aliyun.com/pypi/simple"
    "https://mirrors.cloud.tencent.com/pypi/simple"
    "https://pypi.org/simple"
)
if [[ "$USE_MIRROR" == "true" && -n "${ZLINK_PIP_MIRROR:-}" ]]; then
    # 用户指定了单一镜像, 禁用回退
    PIP_MIRRORS=("$ZLINK_PIP_MIRROR")
fi

# 用法: pip_install_robust -r requirements.txt
# 返回: 0=成功, 1=全部失败
pip_install_robust() {
    set +e
    if [[ ${#PIP_MIRRORS[@]} -eq 0 ]]; then
        info "  尝试 PyPI 官方源"
        if pip install --retries 1 --timeout 15 "$@"; then
            set -e; return 0
        fi
        warn "  PyPI 官方源失败"
        set -e; return 1
    fi
    for mirror in "${PIP_MIRRORS[@]}"; do
        info "  尝试镜像: $mirror"
        if pip install --retries 1 --timeout 15 -i "$mirror" "$@"; then
            ok "  镜像 $mirror 安装成功"
            set -e; return 0
        fi
        warn "  镜像 $mirror 失败, 尝试下一个..."
    done
    set -e
    err "  所有 PyPI 镜像均不可用"
    return 1
}

# ── 更新 Python 依赖 ───────────────────────────────────────────────────────
info "正在更新 Python 依赖..."
if [[ -f "requirements.txt" ]]; then
    if pip_install_robust -r requirements.txt; then
        ok "Python 依赖更新完成"
    else
        warn "Python 依赖更新失败, 可手动运行: source .venv/bin/activate && pip install -r requirements.txt"
    fi
fi

# pyproject.toml 中的依赖
if [[ -f "pyproject.toml" ]]; then
    info "更新 pyproject extras (.[all])..."
    pip_install_robust -e ".[all]" --no-deps || warn "pyproject extras 更新失败 (非阻塞)"
    ok "Python 包依赖已检查"
fi

# 验证依赖图
info "验证依赖图 (pip check)..."
if pip check >/dev/null 2>&1; then
    ok "依赖图一致"
else
    warn "依赖图存在冲突, 但通常不影响运行"
fi

# ── 更新前端依赖 ────────────────────────────────────────────────────────────
if [[ -d "web/node_modules" ]]; then
    info "正在更新前端依赖..."
    (cd web && npm install --silent --no-audit --no-fund 2>/dev/null) && ok "前端依赖更新完成" || warn "前端依赖更新遇到警告，请手动运行 cd web && npm install"
fi

# ── 执行数据迁移 ────────────────────────────────────────────────────────────
info "正在执行数据迁移..."
if python -m scripts.migrate 2>/dev/null; then
    ok "数据迁移完成"
else
    warn "数据迁移执行异常，但不影响系统启动"
    warn "如需手动运行: python -m scripts.migrate"
fi

# ── 恢复暂存更改 ────────────────────────────────────────────────────────────
if $HAD_STASH; then
    info "恢复本地修改..."
    git stash pop 2>/dev/null || warn "本地修改已暂存，可用 'git stash pop' 手动恢复"
fi

# ── 结果输出 ────────────────────────────────────────────────────────────────
# 找最新备份文件用于显示
LATEST_BACKUP=$(ls -1t "$BACKUP_DIR"/zlink-agent-data-*.tar.gz 2>/dev/null | head -1)
BACKUP_SIZE=$(du -h "$LATEST_BACKUP" 2>/dev/null | cut -f1 || echo "-")
BACKUP_NAME=$(basename "$LATEST_BACKUP" 2>/dev/null || echo "无")
echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║            🎉 升级完成                        ║"
echo "╠══════════════════════════════════════════════╣"
echo "║  升级前: $PREVIOUS_HASH"
echo "║  升级后: $NEW_HASH ($NEW_VERSION)"
echo "║  数据备份: $BACKUP_NAME ($BACKUP_SIZE)"
echo "║  备份位置: $BACKUP_DIR/"
echo "║  保留策略: 最近 $BACKUP_RETENTION 份"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── 后续提示 ────────────────────────────────────────────────────────────────
if (( $(echo "$NEW_HASH" | tr -d '\n') != $(echo "$PREVIOUS_HASH" | tr -d '\n') )); then
    info "提示：代码已更新，请重启后端服务以使新代码生效："
    echo ""
    echo "   如果使用 systemd / supervisor："
    echo "     sudo systemctl restart zlink"
    echo ""
    echo "   如果使用 uvicorn 直接运行："
    echo "     按 Ctrl+C 停止，然后重新运行："
    echo "     uvicorn backend.main:app --host 0.0.0.0 --port 8089"
    echo ""
    echo "   如需回滚数据："
    echo "     cd $PROJECT_ROOT"
    echo "     tar -xzf $LATEST_BACKUP"
    echo ""
    echo "   如需回滚代码："
    echo "     git checkout $PREVIOUS_HASH"
    echo ""
fi
