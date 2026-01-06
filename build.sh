#!/bin/bash

# DoiHive 跨平台编译脚本
# Cross-platform build script for DoiHive

set -e

# 颜色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 创建 bin 目录
BIN_DIR="bin"
mkdir -p "$BIN_DIR"

# 项目名称
PROJECT_NAME="doihive"

echo -e "${BLUE}🚀 开始跨平台编译 DoiHive...${NC}\n"

# 编译函数
build() {
    local GOOS=$1
    local GOARCH=$2
    local EXT=$3
    local OUTPUT_NAME="${PROJECT_NAME}"
    
    if [ "$GOOS" = "windows" ]; then
        OUTPUT_NAME="${OUTPUT_NAME}.exe"
    fi
    
    OUTPUT_PATH="${BIN_DIR}/${PROJECT_NAME}-${GOOS}-${GOARCH}${EXT}"
    
    echo -e "${YELLOW}📦 编译 ${GOOS}/${GOARCH}...${NC}"
    
    GOOS=$GOOS GOARCH=$GOARCH go build -ldflags="-s -w" -o "$OUTPUT_PATH" ./cmd
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ ${GOOS}/${GOARCH} 编译成功: ${OUTPUT_PATH}${NC}\n"
    else
        echo -e "${RED}❌ ${GOOS}/${GOARCH} 编译失败${NC}\n"
        exit 1
    fi
}

# 编译各个平台
echo -e "${BLUE}编译目标平台:${NC}"

# Windows (amd64)
build "windows" "amd64" ".exe"

# Linux (amd64)
build "linux" "amd64" ""

# macOS (Intel)
build "darwin" "amd64" ""

# macOS (Apple Silicon)
build "darwin" "arm64" ""

# 显示编译结果
echo -e "${GREEN}✨ 所有平台编译完成！${NC}\n"
echo -e "${BLUE}编译结果位于 ${BIN_DIR}/ 目录:${NC}"
ls -lh "$BIN_DIR" | grep "$PROJECT_NAME" || echo "未找到编译文件"

echo -e "\n${GREEN}🎉 编译完成！${NC}"