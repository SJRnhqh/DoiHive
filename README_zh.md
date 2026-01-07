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
- ✅ **403 防护机制**：完善的浏览器请求头、随机延迟、自动重试机制
- ✅ **验证码绕过**：使用无头浏览器自动绕过机器人验证（Go）
- ✅ **Gzip 解压缩**：自动处理压缩响应
- ✅ **智能错误处理**：详细的错误信息和调试支持
- ✅ **实时进度条**：显示下载进度和实时成功/跳过/失败统计（Go）
- ✅ **日志持久化**：下载日志、失败 DOI 列表、重试列表保存到文件（Go）
- ✅ **直接下载模式**：直接从 DOI 字符串或文件下载 PDF（Go）
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
- `github.com/schollz/progressbar/v3` - 实时进度条和统计信息
- `github.com/chromedp/chromedp` - 无头浏览器用于验证码绕过
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
    # Archive 模式（从 WoS 文件提取 DOI）
    -a, --archive <path>    Archive 目录路径
    -b, --budget <number>   限制下载的 DOI 数量（默认：全部）
    -w, --workers <number>  并发 workers 数量（默认：3）
    -pdf <path>             PDF 输出目录（默认：./pdf）

    # 直接下载模式
    -download               启用直接下载模式
    -doi <string>           要下载的 DOI（逗号分隔）
    -input <path>           包含 DOI 的文件（每行一个）
    -output <path>          PDF 输出目录（默认：./pdf）

    -help                   显示帮助信息
    ```

    **示例**：

    ```bash
    # Archive 模式：使用默认设置下载所有 DOI
    ./bin/doihive-darwin-arm64 -a archive

    # Archive 模式：下载前 100 个 DOI，使用 4 个 workers
    ./bin/doihive-darwin-arm64 -a archive -b 100 -w 4

    # 直接下载：单个 DOI
    ./bin/doihive-darwin-arm64 -download -doi "10.1021/acs.jctc.7b00300" -output pdf

    # 直接下载：多个 DOI
    ./bin/doihive-darwin-arm64 -download -doi "10.1021/xxx,10.1039/yyy" -output pdf

    # 直接下载：从 DOI 列表文件（例如重试失败的 DOI）
    ./bin/doihive-darwin-arm64 -download -input pdf/logs/retry_dois.txt -output pdf

    # 对于大批量下载，可以增加 workers（但可能增加 403 风险）
    ./bin/doihive-darwin-arm64 -a archive -b 1000 -w 8
    ```

4. **输出**：
   - PDF 文件保存到 `pdf/` 目录（或指定目录）
   - 失败的 HTML 页面保存到 `pdf/debug/` 用于调试（仅保存未知错误）
   - **日志文件**保存到 `pdf/logs/`：
     - `download_log_<时间戳>.txt` - 完整下载日志
     - `failed_dois_<时间戳>.txt` - 失败 DOI 详细信息
     - `retry_dois_<时间戳>.txt` - 纯 DOI 列表（方便重试）
   - **实时进度条**显示下载进度和实时成功/跳过/失败统计
   - 错误信息显示在控制台
   - 详细统计信息，包括吞吐量和平均墙钟时间

    **进度条示例**：

    ```shell
    📥 下载中 [✅5 ⏭️0 ❌2] [=========>--------] 7/20 35% 2.3 it/s
    ```

    **日志文件示例**：

    ```shell
    📝 日志文件已保存:
      📄 完整日志: pdf/logs/download_log_2026-01-07_20-22-06.txt
      ❌ 失败详情: pdf/logs/failed_dois_2026-01-07_20-22-06.txt
      🔄 重试列表: pdf/logs/retry_dois_2026-01-07_20-22-06.txt
    ```

### 工作流程

1. **DOI 提取**：脚本扫描 `archive/` 目录中的所有 `.txt` 文件并提取 DOI
2. **DOI 验证**：检查缺失的 DOI 并提供详细的统计信息
3. **URL 构造**：从提取的 DOI 构建 Sci-Hub URL
4. **PDF 下载**：使用多线程请求下载 PDF
5. **错误处理**：记录失败的下载并提供详细的错误信息

### 403 防护机制

Python 和 Go 实现都包含完善的 403 错误防护：

- **完善的浏览器请求头**：完整的 User-Agent、Accept、Accept-Language 等请求头，模拟真实浏览器
- **随机延迟**：每次请求前随机延迟 0.5-2.0 秒，避免被识别为爬虫
- **自动重试**：遇到 403 错误时自动重试最多 3 次，延迟递增
- **Referer 头**：PDF 下载时添加 Referer 头，表明来源页面
- **低并发默认设置**：默认 3 个 workers，最小化触发频率限制的风险

**推荐设置**：

- **默认（3 workers）**：最安全，成功率约 65-80%，适合大多数场景
- **4 workers**：仍然安全，速度稍快
- **2 workers**：最保守，如果遇到 403 错误可以使用

### 性能对比

| 版本 | 并发数 | 吞吐量（任务/秒） | 成功率 | 适用场景 |
| ------ | -------- | ------------------ | -------- | ---------- |
| **Go** | 3（默认） | ~2-3 | ~65-80% | 所有场景（推荐） |
| **Go** | 4-8 | ~3-5 | ~60-75% | 中等批量，可接受风险 |
| **Python** | 3（默认） | ~1-2 | ~65-80% | 中小规模下载 |

**建议**：

- **< 1000 任务**：默认设置（3 workers）对两个版本都很好
- **1000-3000 任务**：推荐 Go 版本（快 2-3 倍，同样安全）
- **> 3000 任务**：强烈推荐 Go 版本，可考虑使用 4 workers 以获得更好的吞吐量

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
│   ├── hive.go            # PDF 下载逻辑（含验证码绕过）
│   └── logger.go          # 日志持久化
├── bin/                   # 编译后的二进制文件（生成）
├── archive/               # 输入：WoS TXT 文件
├── pdf/                   # 输出：下载的 PDF
│   ├── logs/              # 输出：下载日志（Go）
│   └── debug/             # 输出：调试 HTML 文件
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
- [x] **403 防护机制**：完善的浏览器请求头、随机延迟、重试机制
- [x] **验证码绕过**：使用无头浏览器自动绕过机器人验证（Go）
- [x] **Gzip 解压缩**：自动处理压缩的 HTML/PDF 响应
- [x] **智能错误检测**：识别不可用文章、验证码页面等
- [x] **实时进度条**：显示下载进度和实时统计（Go）
- [x] **日志持久化**：下载日志、失败 DOI 列表、重试列表（Go）
- [x] **直接下载模式**：从 DOI 字符串或文件直接下载（Go）
- [x] 错误处理和日志记录
- [x] 美观的控制台输出和进度跟踪（Python）
- [x] 详细的统计信息和摘要
- [x] HTTP 连接池优化性能
- [x] 可配置的并发数和下载限制
- [x] 性能指标（吞吐量、平均墙钟时间等）
- [x] 跨平台编译支持（Go）
- [x] 调试 HTML 保存功能（仅保存未知错误）

### 🚧 进行中 / 计划中

- [ ] 从搜索查询自动获取 DOI
- [ ] 支持其他文献数据源（除 WoS 外）
- [ ] 配置文件支持
- [ ] 多个 Sci-Hub 镜像支持
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
