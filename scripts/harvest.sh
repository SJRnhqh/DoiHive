#!/bin/bash
#
# harvest.sh - DoiHive 安全渐进式爬取脚本
#
# 特点：
#   - 小批量循环下载，降低反爬风险
#   - 批次间随机等待，模拟人类行为
#   - 自动检测异常（高错误率+低成功率）并停止
#   - 借助缓存机制实现断点续传
#
# 用法：
#   ./scripts/harvest.sh -a <archive_dir> [options]
#
# 示例：
#   ./scripts/harvest.sh -a ./archive                    # 使用默认参数
#   ./scripts/harvest.sh -a ./archive -b 50 -r 10       # 每批50个，共10轮
#   ./scripts/harvest.sh -a ./archive -b 30 -w 2 -d 120 # 每批30个，2并发，间隔120秒
#

set -e

# ==================== 配置参数 ====================

# 默认值
ARCHIVE_DIR=""
BATCH_SIZE=30           # 每批下载数量
MAX_ROUNDS=0            # 最大轮数（0=无限制，直到全部完成）
WORKERS=2               # 并发数
MIN_DELAY=60            # 批次间最小等待秒数
MAX_DELAY=180           # 批次间最大等待秒数
PDF_DIR="./pdf"         # PDF 输出目录

# 异常检测阈值
ERROR_THRESHOLD=0.8     # 错误率阈值（超过此值视为异常）
MIN_SUCCESS=2           # 最小成功数（低于此值且错误率高则停止）

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ==================== 帮助信息 ====================

show_help() {
    cat << EOF
🐝 DoiHive Harvest - 安全渐进式爬取脚本

用法: $0 -a <archive_dir> [options]

必需参数:
    -a, --archive <dir>     Archive 目录路径（包含 WoS TXT 文件）

可选参数:
    -b, --batch <num>       每批下载数量 (默认: $BATCH_SIZE)
    -r, --rounds <num>      最大轮数，0=无限制 (默认: $MAX_ROUNDS)
    -w, --workers <num>     并发 worker 数 (默认: $WORKERS)
    -d, --delay <sec>       批次间最小等待秒数 (默认: $MIN_DELAY)
    -D, --max-delay <sec>   批次间最大等待秒数 (默认: $MAX_DELAY)
    -p, --pdf <dir>         PDF 输出目录 (默认: $PDF_DIR)
    -e, --error-rate <0-1>  错误率阈值 (默认: $ERROR_THRESHOLD)
    -s, --min-success <num> 最小成功数阈值 (默认: $MIN_SUCCESS)
    -h, --help              显示此帮助信息

示例:
    $0 -a ./archive                         # 默认参数运行
    $0 -a ./archive -b 50 -r 10             # 每批50个，共10轮
    $0 -a ./archive -b 20 -w 1 -d 180       # 保守模式：20个/批，单线程，间隔3分钟
    $0 -a ./archive -e 0.6 -s 5             # 更严格的异常检测

EOF
}

# ==================== 参数解析 ====================

while [[ $# -gt 0 ]]; do
    case $1 in
        -a|--archive)
            ARCHIVE_DIR="$2"
            shift 2
            ;;
        -b|--batch)
            BATCH_SIZE="$2"
            shift 2
            ;;
        -r|--rounds)
            MAX_ROUNDS="$2"
            shift 2
            ;;
        -w|--workers)
            WORKERS="$2"
            shift 2
            ;;
        -d|--delay)
            MIN_DELAY="$2"
            shift 2
            ;;
        -D|--max-delay)
            MAX_DELAY="$2"
            shift 2
            ;;
        -p|--pdf)
            PDF_DIR="$2"
            shift 2
            ;;
        -e|--error-rate)
            ERROR_THRESHOLD="$2"
            shift 2
            ;;
        -s|--min-success)
            MIN_SUCCESS="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}❌ 未知参数: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# 检查必需参数
if [[ -z "$ARCHIVE_DIR" ]]; then
    echo -e "${RED}❌ 错误: 必须指定 archive 目录 (-a)${NC}"
    show_help
    exit 1
fi

if [[ ! -d "$ARCHIVE_DIR" ]]; then
    echo -e "${RED}❌ 错误: 目录不存在: $ARCHIVE_DIR${NC}"
    exit 1
fi

# ==================== 工具函数 ====================

# 获取随机延迟时间
random_delay() {
    echo $(( MIN_DELAY + RANDOM % (MAX_DELAY - MIN_DELAY + 1) ))
}

# 格式化时间
format_duration() {
    local seconds=$1
    if (( seconds < 60 )); then
        echo "${seconds}s"
    elif (( seconds < 3600 )); then
        echo "$(( seconds / 60 ))m$(( seconds % 60 ))s"
    else
        echo "$(( seconds / 3600 ))h$(( (seconds % 3600) / 60 ))m"
    fi
}

# 获取当前时间戳
timestamp() {
    date "+%Y-%m-%d %H:%M:%S"
}

# 日志函数
log_info() {
    echo -e "${BLUE}[$(timestamp)]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(timestamp)]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[$(timestamp)]${NC} $1"
}

log_error() {
    echo -e "${RED}[$(timestamp)]${NC} $1"
}

# ==================== 主逻辑 ====================

# 检测 doihive 可执行文件
DOIHIVE_BIN=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 按优先级查找可执行文件
if [[ -x "$PROJECT_DIR/bin/doihive-darwin-arm64" ]]; then
    DOIHIVE_BIN="$PROJECT_DIR/bin/doihive-darwin-arm64"
elif [[ -x "$PROJECT_DIR/bin/doihive-darwin-amd64" ]]; then
    DOIHIVE_BIN="$PROJECT_DIR/bin/doihive-darwin-amd64"
elif [[ -x "$PROJECT_DIR/bin/doihive-linux-amd64" ]]; then
    DOIHIVE_BIN="$PROJECT_DIR/bin/doihive-linux-amd64"
elif command -v doihive &> /dev/null; then
    DOIHIVE_BIN="doihive"
else
    log_error "❌ 找不到 doihive 可执行文件"
    log_info "请先运行 ./build.sh 或将 doihive 添加到 PATH"
    exit 1
fi

log_info "🐝 DoiHive Harvest 启动"
echo ""
echo -e "  📂 Archive:     ${CYAN}$ARCHIVE_DIR${NC}"
echo -e "  📁 PDF 目录:    ${CYAN}$PDF_DIR${NC}"
echo -e "  📦 批次大小:    ${CYAN}$BATCH_SIZE${NC}"
echo -e "  👷 并发数:      ${CYAN}$WORKERS${NC}"
echo -e "  ⏰ 间隔范围:    ${CYAN}${MIN_DELAY}s - ${MAX_DELAY}s${NC}"
echo -e "  🎯 最大轮数:    ${CYAN}$([ $MAX_ROUNDS -eq 0 ] && echo '无限制' || echo $MAX_ROUNDS)${NC}"
echo -e "  ⚠️  错误阈值:   ${CYAN}$(echo "$ERROR_THRESHOLD * 100" | bc)%${NC}"
echo -e "  🔧 可执行文件:  ${CYAN}$DOIHIVE_BIN${NC}"
echo ""

# 统计变量
ROUND=0
TOTAL_SUCCESS=0
TOTAL_FAILED=0
TOTAL_SKIPPED=0
START_TIME=$(date +%s)
CONSECUTIVE_BAD_ROUNDS=0  # 连续异常轮数

# 信号处理 - 优雅退出
cleanup() {
    echo ""
    log_warn "🛑 收到中断信号，正在停止..."
    show_summary
    exit 130
}
trap cleanup SIGINT SIGTERM

# 显示最终统计
show_summary() {
    local end_time=$(date +%s)
    local duration=$((end_time - START_TIME))
    
    echo ""
    echo -e "${CYAN}════════════════════════════════════════${NC}"
    echo -e "${CYAN}           📊 收割统计汇总              ${NC}"
    echo -e "${CYAN}════════════════════════════════════════${NC}"
    echo ""
    echo -e "  🔄 完成轮数:    ${GREEN}$ROUND${NC}"
    echo -e "  ✅ 总成功:      ${GREEN}$TOTAL_SUCCESS${NC}"
    echo -e "  ❌ 总失败:      ${RED}$TOTAL_FAILED${NC}"
    echo -e "  ⏭️  总跳过:      ${YELLOW}$TOTAL_SKIPPED${NC}"
    echo -e "  ⏱️  总耗时:      ${BLUE}$(format_duration $duration)${NC}"
    echo ""
}

# 主循环
while true; do
    ROUND=$((ROUND + 1))
    
    # 检查轮数限制
    if [[ $MAX_ROUNDS -gt 0 && $ROUND -gt $MAX_ROUNDS ]]; then
        log_success "🎉 已完成设定的 $MAX_ROUNDS 轮，停止运行"
        break
    fi
    
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    log_info "🚀 开始第 $ROUND 轮下载"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    # 执行下载，流式输出同时捕获结果
    TEMP_OUTPUT=$(mktemp)
    "$DOIHIVE_BIN" -a "$ARCHIVE_DIR" -b "$BATCH_SIZE" -w "$WORKERS" --pdf "$PDF_DIR" 2>&1 | tee "$TEMP_OUTPUT" || true
    OUTPUT=$(cat "$TEMP_OUTPUT")
    rm -f "$TEMP_OUTPUT"
    
    # 解析统计信息
    SUCCESS=$(echo "$OUTPUT" | grep -E "^✅ 成功:" | grep -oE '[0-9]+' | head -1 || echo "0")
    FAILED=$(echo "$OUTPUT" | grep -E "^❌ 失败:" | grep -oE '[0-9]+' | head -1 || echo "0")
    SKIPPED=$(echo "$OUTPUT" | grep -E "^⏭️  跳过:" | grep -oE '[0-9]+' | head -1 || echo "0")
    
    # 检查是否所有都被缓存跳过
    if echo "$OUTPUT" | grep -q "所有 DOI 已在缓存中"; then
        log_success "🎉 所有 DOI 已处理完成！"
        break
    fi
    
    # 累计统计
    TOTAL_SUCCESS=$((TOTAL_SUCCESS + SUCCESS))
    TOTAL_FAILED=$((TOTAL_FAILED + FAILED))
    TOTAL_SKIPPED=$((TOTAL_SKIPPED + SKIPPED))
    
    # 计算本轮实际处理数和错误率
    PROCESSED=$((SUCCESS + FAILED))
    if [[ $PROCESSED -gt 0 ]]; then
        ERROR_RATE=$(echo "scale=2; $FAILED / $PROCESSED" | bc)
    else
        ERROR_RATE="0"
    fi
    
    log_info "📊 本轮统计: ✅ $SUCCESS  ❌ $FAILED  ⏭️ $SKIPPED  (错误率: ${ERROR_RATE})"
    
    # 异常检测：高错误率 + 低成功数
    IS_BAD_ROUND=false
    if (( $(echo "$ERROR_RATE >= $ERROR_THRESHOLD" | bc -l) )) && [[ $SUCCESS -lt $MIN_SUCCESS ]]; then
        IS_BAD_ROUND=true
        CONSECUTIVE_BAD_ROUNDS=$((CONSECUTIVE_BAD_ROUNDS + 1))
        log_warn "⚠️  检测到异常: 错误率 ${ERROR_RATE} >= ${ERROR_THRESHOLD}，成功数 $SUCCESS < $MIN_SUCCESS"
        log_warn "⚠️  连续异常轮数: $CONSECUTIVE_BAD_ROUNDS"
    else
        CONSECUTIVE_BAD_ROUNDS=0
    fi
    
    # 连续2轮异常则停止
    if [[ $CONSECUTIVE_BAD_ROUNDS -ge 2 ]]; then
        log_error "🚨 连续 $CONSECUTIVE_BAD_ROUNDS 轮异常，自动停止！"
        log_error "🚨 可能原因: IP 被封禁 / 触发反爬机制 / 网络问题"
        log_info "💡 建议: 等待一段时间后重试，或更换网络环境"
        break
    fi
    
    # 如果还有更多要下载，等待后继续
    DELAY=$(random_delay)
    
    if [[ $IS_BAD_ROUND == true ]]; then
        # 异常轮次，增加等待时间
        DELAY=$((DELAY * 2))
        log_warn "⏳ 检测到异常，延长等待时间: $(format_duration $DELAY)"
    else
        log_info "⏳ 等待 $(format_duration $DELAY) 后开始下一轮..."
    fi
    
    # 显示倒计时
    for ((i=DELAY; i>0; i--)); do
        printf "\r  ⏳ 剩余等待: %-6s" "$(format_duration $i)"
        sleep 1
    done
    printf "\r                        \r"
    
done

show_summary
log_success "✨ Harvest 完成!"

