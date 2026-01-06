# 🐝 DoiHive

![DoiHive Logo](image/DoiHive.png)

> **一个跨语言（Python/Go）的学术 PDF 批量下载工具**
>
> 目前支持从 Web of Science (WoS) 导出的 TXT 文件中提取 DOI，并通过 Sci-Hub 下载 PDF

[English](README.md) • [中文文档](README_zh.md)

---

## 项目简介

DoiHive 自动化了从文献数据文件中提取 DOI 并下载对应 PDF 的过程。项目最终目标是支持从搜索查询自动获取 DOI，但目前专注于处理已有的 DOI 数据。

**当前状态**：Python 和 Go 实现均已完成核心功能。Go 版本在大规模下载场景下性能更优。

## 功能特性

- ✅ 从 WoS 导出的 TXT 文件中提取 DOI
- ✅ 从 Sci-Hub 批量下载 PDF
- ✅ 高性能并发下载（Python 多线程，Go goroutines）
- ✅ 完善的错误日志和报告
- ✅ 美观的控制台输出和进度跟踪（Python）
- ✅ 详细的统计信息和摘要
- ✅ 可配置的并发数和下载限制
- ✅ 性能指标（吞吐量、平均墙钟时间等）

## 技术栈

### Python (当前)

![Python](https://img.shields.io/badge/Python-3.13+-blue?logo=python&logoColor=white)

- **Python 3.13+**
- `beautifulsoup4` - 用于提取 PDF URL 的 HTML 解析
- `requests` - 用于下载的 HTTP 请求
- `rich` - 美观的终端输出和进度条

### Go (当前)

![Go](https://img.shields.io/badge/Go-1.25+-00ADD8?logo=go&logoColor=white)

- **Go 1.25+**
- `github.com/PuerkitoBio/goquery` - 用于提取 PDF URL 的 HTML 解析
- 高性能 goroutines 并发下载
- HTTP 连接池优化性能
- 跨平台编译支持

## 安装

### 前置要求

**Python 版本：**

- Python 3.13 或更高版本
- [uv](https://github.com/astral-sh/uv)（推荐）或 pip

**Go 版本：**

- Go 1.25 或更高版本

### 设置

1. 克隆仓库：

    ```bash
    git clone https://github.com/SJRnhqh/DoiHive.git
    cd DoiHive
    ```

2. **Python 版本**：使用 uv 安装依赖：

    ```bash
    uv sync
    ```

    或使用 pip：

    ```bash
    pip install -e .
    ```

3. **Go 版本**：安装依赖：

    ```bash
    go mod download
    ```

    编译可执行文件：

    ```bash
    ./build.sh
    ```

    或手动编译：

    ```bash
    go build -o bin/doihive ./cmd
    ```

## 使用方法

### Python 实现

1. **准备 WoS TXT 文件**：将 Web of Science 导出的 TXT 文件放置在 `archive/` 目录中。

2. **运行脚本**：

    ```bash
    cd python
    python main.py
    ```

3. **输出**：
   - PDF 文件保存到 `pdf/` 目录
   - 错误日志保存到 `error/` 目录（JSON 格式）
   - 应用日志保存到 `logs/` 目录

### Go 实现（推荐用于大规模下载）

1. **准备 WoS TXT 文件**：将 Web of Science 导出的 TXT 文件放置在 `archive/` 目录中。

2. **运行可执行文件**：

    ```bash
    ./bin/doihive-darwin-arm64 -a archive
    ```

    或编译后运行：

    ```bash
    go run ./cmd -a archive
    ```

3. **命令行参数**：

    ```bash
    -a, --archive <path>    Archive 目录路径（必需）
    -b, --budget <number>   限制下载的 DOI 数量（默认：全部）
    -w, --workers <number>  并发 workers 数量（默认：16）
    -pdf <path>             PDF 输出目录（默认：./pdf）
    -help                   显示帮助信息
    ```

    **示例**：

    ```bash
    # 使用默认设置下载所有 DOI（16 个 workers）
    ./bin/doihive-darwin-arm64 -a archive

    # 下载前 100 个 DOI，使用 64 个 workers
    ./bin/doihive-darwin-arm64 -a archive -b 100 -w 64

    # 下载到自定义目录
    ./bin/doihive-darwin-arm64 -a archive -pdf ./downloads
    ```

4. **输出**：
   - PDF 文件保存到 `pdf/` 目录（或指定目录）
   - 错误信息显示在控制台
   - 详细统计信息，包括吞吐量和平均墙钟时间

### 工作流程

1. **DOI 提取**：脚本扫描 `archive/` 目录中的所有 `.txt` 文件并提取 DOI
2. **DOI 验证**：检查缺失的 DOI 并提供详细的统计信息
3. **URL 构造**：从提取的 DOI 构建 Sci-Hub URL
4. **PDF 下载**：使用多线程请求下载 PDF
5. **错误处理**：记录失败的下载并提供详细的错误信息

### 性能对比

| 版本 | 并发数 | 吞吐量（任务/秒） | 适用场景 |
| ------ | -------- | ------------------ | ---------- |
| **Go** | 64-128 | ~18-23 | 大规模下载（1000+ 任务） |
| **Python** | 16-32 | ~7-10 | 中小规模下载（<1000 任务） |

**建议**：

- **< 1000 任务**：两个版本都可以
- **1000-3000 任务**：推荐 Go 版本（快 2-3 倍）
- **> 3000 任务**：强烈推荐 Go 版本（显著节省时间）

## 项目结构

```txt
DoiHive/
├── python/                 # Python 实现
│   ├── main.py            # 主入口点
│   └── utils/             # 工具模块
│       ├── analyze.py     # DOI 提取和验证
│       ├── hive.py        # PDF 下载逻辑
│       └── logger.py      # 日志配置
├── cmd/                   # Go 实现
│   └── main.go            # 主入口点（CLI）
├── core/                  # Go 核心逻辑
│   ├── check.go           # DOI 检查和提取
│   └── hive.go            # PDF 下载逻辑
├── bin/                   # 编译后的二进制文件（生成）
├── archive/               # 输入：WoS TXT 文件
├── pdf/                   # 输出：下载的 PDF
├── error/                 # 输出：错误日志（Python）
├── logs/                  # 输出：应用日志（Python）
├── build.sh               # 跨平台编译脚本
├── pyproject.toml         # Python 依赖
└── go.mod                 # Go 依赖
```

## 开发路线图

### ✅ 已完成

- [x] 从 WoS TXT 文件提取 DOI
- [x] 验证和检查 DOI 完整性
- [x] 从 DOI 构造 Sci-Hub URL
- [x] 多线程批量下载 PDF（Python）
- [x] 高性能 goroutines 并发下载（Go）
- [x] 错误处理和日志记录
- [x] 美观的控制台输出和进度跟踪（Python）
- [x] 详细的统计信息和摘要
- [x] HTTP 连接池优化性能
- [x] 可配置的并发数和下载限制
- [x] 性能指标（吞吐量、平均墙钟时间等）
- [x] 跨平台编译支持（Go）

### 🚧 进行中 / 计划中

- [ ] 从搜索查询自动获取 DOI
- [ ] 支持其他文献数据源（除 WoS 外）
- [ ] 配置文件支持
- [ ] 恢复中断的下载
- [ ] 速率限制和重试机制
- [ ] 多个 Sci-Hub 镜像支持
- [ ] 大规模下载的进度持久化
- [ ] 分布式处理支持

### 🎯 未来目标

- [ ] 端到端自动化：搜索查询 → DOI 获取 → PDF 下载
- [ ] Web 界面
- [ ] API 支持
- [ ] 数据库集成用于 DOI 管理

## 贡献

欢迎贡献！请随时提交 Pull Request。

## 免责声明

本工具仅用于教育和研究目的。下载学术论文时，请遵守版权法和出版商的服务条款。
