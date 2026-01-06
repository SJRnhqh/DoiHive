# DoiHive

一个跨语言（Python/Go）的学术 PDF 批量下载工具。目前支持从 Web of Science (WoS) 导出的 TXT 文件中提取 DOI，并通过 Sci-Hub 下载 PDF。

[English](README.md) | [中文文档](README_zh.md)

## 项目简介

DoiHive 自动化了从文献数据文件中提取 DOI 并下载对应 PDF 的过程。项目最终目标是支持从搜索查询自动获取 DOI，但目前专注于处理已有的 DOI 数据。

**当前状态**：Python 实现已完成。Go 实现计划中。

## 功能特性

- ✅ 从 WoS 导出的 TXT 文件中提取 DOI
- ✅ 从 Sci-Hub 批量下载 PDF
- ✅ 多线程下载以提高性能
- ✅ 完善的错误日志和报告
- ✅ 美观的控制台输出和进度跟踪
- ✅ 详细的统计信息和摘要

## 技术栈

### Python (当前)

![Python](https://img.shields.io/badge/Python-3.13+-blue?logo=python&logoColor=white)

- **Python 3.13+**
- `beautifulsoup4` - 用于提取 PDF URL 的 HTML 解析
- `requests` - 用于下载的 HTTP 请求
- `rich` - 美观的终端输出和进度条

### Go (计划中)

- Go 实现以提升性能

## 安装

### 前置要求

- Python 3.13 或更高版本
- [uv](https://github.com/astral-sh/uv)（推荐）或 pip

### 设置

1. 克隆仓库：

    ```bash
    git clone https://github.com/SJRnhqh/DoiHive.git
    cd DoiHive
    ```

2. 使用 uv 安装依赖：

    ```bash
    uv sync
    ```

    或使用 pip：

    ```bash
    pip install -e .
    ```

## 使用方法

### 当前实现（Python）

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

### 工作流程

1. **DOI 提取**：脚本扫描 `archive/` 目录中的所有 `.txt` 文件并提取 DOI
2. **DOI 验证**：检查缺失的 DOI 并提供详细的统计信息
3. **URL 构造**：从提取的 DOI 构建 Sci-Hub URL
4. **PDF 下载**：使用多线程请求下载 PDF
5. **错误处理**：记录失败的下载并提供详细的错误信息

### 配置

可以在 `python/main.py` 中修改以下内容：

- 要处理的 URL 数量（当前测试限制为 10：`urls[:10]`）
- Sci-Hub 基础 URL（默认：`https://sci-hub.se`）
- 输出目录（`pdf/`、`error/`、`logs/`）

## 项目结构

```txt
DoiHive/
├── python/                 # Python 实现
│   ├── main.py            # 主入口点
│   └── utils/             # 工具模块
│       ├── analyze.py     # DOI 提取和验证
│       ├── hive.py        # PDF 下载逻辑
│       └── logger.py      # 日志配置
├── cmd/                   # Go 实现（计划中）
│   └── main.go
├── archive/               # 输入：WoS TXT 文件
├── pyproject.toml         # Python 依赖
└── go.mod                 # Go 依赖（计划中）
```

## 开发路线图

### ✅ 已完成

- [x] 从 WoS TXT 文件提取 DOI
- [x] 验证和检查 DOI 完整性
- [x] 从 DOI 构造 Sci-Hub URL
- [x] 多线程批量下载 PDF
- [x] 错误处理和日志记录
- [x] 美观的控制台输出和进度跟踪
- [x] 详细的统计信息和摘要

### 🚧 进行中 / 计划中

- [ ] Go 实现
- [ ] 从搜索查询自动获取 DOI
- [ ] 支持其他文献数据源（除 WoS 外）
- [ ] 配置文件支持
- [ ] 恢复中断的下载
- [ ] 速率限制和重试机制
- [ ] 多个 Sci-Hub 镜像支持

### 🎯 未来目标

- [ ] 端到端自动化：搜索查询 → DOI 获取 → PDF 下载
- [ ] Web 界面
- [ ] API 支持
- [ ] 数据库集成用于 DOI 管理

## 贡献

欢迎贡献！请随时提交 Pull Request。

## 免责声明

本工具仅用于教育和研究目的。下载学术论文时，请遵守版权法和出版商的服务条款。
