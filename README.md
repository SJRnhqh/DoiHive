# 🐝 DoiHive

![DoiHive Logo](image/DoiHive-logo.png)

> **A cross-language (Python/Go) tool for batch downloading academic PDFs from DOIs**
>
> Currently supports extracting DOIs from Web of Science (WoS) exported TXT files and downloading PDFs via Sci-Hub

[中文文档](README_zh.md) • [English](README.md)

---

## Overview

DoiHive automates the process of extracting DOIs from bibliographic data files and downloading corresponding PDFs. The project aims to eventually support automatic DOI retrieval from search queries, but currently focuses on processing existing DOI data.

**Current Status**: Both Python and Go implementations are complete with core functionality. Go version offers superior performance for large-scale downloads.

![DoiHive Workflow](image/DoiHive.png)

> **Vision**: `🔍 Topic → 🐝 OpenAlex → 🏠 DOI List → 🍯 Sci-Hub → 🌾 Harvest → 📄 PDF → 🤖 AI Pipeline`
>
> End-to-end academic literature collection: from topic search to AI training data

## Features

- ✅ Extract DOIs from WoS TXT files, batch download PDFs
- ✅ **Anti-crawl**: Browser headers, random delays, auto-retry
- ✅ **DOI cache**: Resume support, skip processed DOIs
- ✅ **Safe harvest**: Gradual downloading, auto-stop on anomalies
- ✅ **Real-time progress**: Progress bar, statistics, log persistence

## Tech Stack

![Python](https://img.shields.io/badge/Python-3.13+-blue?logo=python&logoColor=white)
![Go](https://img.shields.io/badge/Go-1.25+-00ADD8?logo=go&logoColor=white)

- **Python 3.13+** - Basic implementation
- **Go 1.25+** - High-performance implementation (recommended)

### Performance Comparison

| Metric | Python | Go (default 3 workers) |
| -------- | -------- | ----- |
| Time per task | - | ~400-600ms |
| Concurrency | Single-threaded | Goroutines |
| Throughput | - | ~2 DOI/s |
| Cache/Anti-crawl | ❌ | ✅ |
| Recommended for | Small-scale testing | Large-scale batch downloads |

> ⚠️ Python version lacks cache and anti-crawl mechanisms, not recommended for large-scale downloads

## Installation

### Prerequisites

**For Python:**

- Python 3.13 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

**For Go:**

- Go 1.25 or higher

### Setup

1. Clone the repository:

    ```bash
    git clone https://github.com/SJRnhqh/DoiHive.git
    cd DoiHive
    ```

2. **For Python**: Install dependencies using uv:

    ```bash
    uv sync
    ```

    Or using pip:

    ```bash
    pip install -e .
    ```

3. **For Go**: Install dependencies:

    ```bash
    go mod download
    ```

    Build the executable:

    ```bash
    ./build.sh
    ```

    Or build manually:

    ```bash
    go build -o bin/doihive ./cmd
    ```

## Usage

### Python Implementation

1. **Prepare WoS TXT files**: Place your Web of Science exported TXT files in the `archive/` directory.

2. **Run the script**:

    ```bash
    cd python
    python main.py
    ```

3. **Output**:
    - PDFs are saved to `pdf/` directory
    - Error logs are saved to `error/` directory (JSON format)
    - Application logs are saved to `logs/` directory

### Go Implementation (Recommended)

```bash
./bin/doihive-darwin-arm64 -a archive -b 100 -w 2
```

| Option | Description | Default |
| -------- | ------------- | --------- |
| `-a` | Archive directory (required) | - |
| `-b` | Limit download count (0=all) | 0 |
| `-w` | Concurrent workers | 3 |
| `-pdf` | PDF output directory | ./pdf |

**Output directories**: `pdf/` (PDFs), `pdf/logs/` (logs), `pdf/debug/` (debug)

### Safe Harvest (Recommended for Large-Scale)

```bash
./scripts/harvest.sh -a ./archive                    # Default settings
./scripts/harvest.sh -a ./archive -b 50 -r 10        # 50 per batch, 10 rounds
```

| Option | Description | Default |
| -------- | ------------- | --------- |
| `-a` | Archive directory (required) | - |
| `-b` | Batch size per round | 30 |
| `-r` | Max rounds (0=unlimited) | 0 |
| `-w` | Concurrent workers | 3 |
| `-d` | Min delay between batches (sec) | 60 |
| `-D` | Max delay between batches (sec) | 180 |

## Project Structure

```txt
DoiHive/
├── python/                 # Python implementation
│   ├── main.py            # Main entry point
│   └── utils/             # Utility modules
│       ├── analyze.py     # DOI extraction and validation
│       ├── hive.py        # PDF download logic
│       └── logger.py      # Logging configuration
├── cmd/                   # Go implementation
│   └── main.go            # Main entry point (CLI)
├── core/                  # Go core logic
│   ├── check.go           # DOI checking and extraction
│   ├── hive.go            # PDF download logic (with cache & anti-crawl)
│   └── logger.go          # Log persistence
├── scripts/               # Automation scripts
│   └── harvest.sh         # Safe gradual batch download script
├── bin/                   # Compiled binaries (generated)
├── archive/               # Input: WoS TXT files
├── pdf/                   # Output: Downloaded PDFs
│   ├── downloaded.txt     # Cache: successfully downloaded DOIs
│   ├── not_available.txt  # Cache: unavailable DOIs on Sci-Hub
│   ├── logs/              # Output: Download logs (Go)
│   └── debug/             # Output: Debug HTML files
├── error/                 # Output: Error logs (Python)
├── logs/                  # Output: Application logs (Python)
├── build.sh               # Cross-platform build script
├── pyproject.toml         # Python dependencies
└── go.mod                 # Go dependencies
```

## Development Roadmap

### ✅ Completed

- [x] WoS TXT file DOI extraction & validation
- [x] Sci-Hub batch download (Python/Go dual implementation)
- [x] Anti-crawl: browser headers, random delays, auto-retry
- [x] DOI cache & resume support
- [x] Safe harvest script (gradual downloading)
- [x] Real-time progress bar & log persistence

### 🚧 Planned

- [ ] Multiple Sci-Hub mirror support
- [ ] Other bibliographic data sources
- [ ] Configuration file support

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Disclaimer

This tool is for educational and research purposes only. Please respect copyright laws and publisher terms of service when downloading academic papers.
