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

## Features

- ✅ Extract DOIs from WoS exported TXT files
- ✅ Batch download PDFs from Sci-Hub
- ✅ High-performance concurrent downloads (multi-threading in Python, goroutines in Go)
- ✅ **Anti-403 protection**: Complete browser headers, random delays, automatic retry mechanism
- ✅ **CAPTCHA bypass**: Automatic robot verification bypass using headless browser (Go)
- ✅ **Gzip decompression**: Automatic handling of compressed responses
- ✅ **Smart error handling**: Detailed error messages and debugging support
- ✅ **Real-time progress bar**: Live progress tracking with success/skip/failed counts (Go)
- ✅ **Log persistence**: Download logs, failed DOIs, and retry lists saved to files (Go)
- ✅ **DOI cache**: Skip processed DOIs without network requests (Go)
- ✅ **Safe harvest script**: Gradual batch downloading with auto-stop on anomalies (Go)
- ✅ **Direct download mode**: Download PDFs directly from DOI strings or files (Go)
- ✅ Comprehensive error logging and reporting
- ✅ Beautiful console output with progress tracking (Python)
- ✅ Detailed statistics and summaries
- ✅ Configurable concurrency and download limits
- ✅ Performance metrics (throughput, average wall-clock time, etc.)

## Tech Stack

### Python (Current)

![Python](https://img.shields.io/badge/Python-3.13+-blue?logo=python&logoColor=white)

- **Python 3.13+**
- `beautifulsoup4` - HTML parsing for PDF URL extraction
- `requests` - HTTP requests for downloading
- `rich` - Beautiful terminal output and progress bars

### Go (Current)

![Go](https://img.shields.io/badge/Go-1.25+-00ADD8?logo=go&logoColor=white)

- **Go 1.25+**
- `github.com/PuerkitoBio/goquery` - HTML parsing for PDF URL extraction
- `github.com/schollz/progressbar/v3` - Real-time progress bar with live statistics
- `github.com/chromedp/chromedp` - Headless browser for CAPTCHA bypass
- High-performance goroutines for concurrent downloads
- HTTP connection pooling for optimal performance
- Cross-platform compilation support

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

### Go Implementation (Recommended for Large-Scale Downloads)

1. **Prepare WoS TXT files**: Place your Web of Science exported TXT files in the `archive/` directory.

2. **Run the executable**:

    ```bash
    ./bin/doihive-darwin-arm64 -a archive
    ```

    Or build and run:

    ```bash
    go run ./cmd -a archive
    ```

3. **Command-line Options**:

    ```bash
    # Archive mode (extract DOIs from WoS files)
    -a, --archive <path>    Archive directory path
    -b, --budget <number>   Limit number of DOIs to download (default: all)
    -w, --workers <number>  Number of concurrent workers (default: 3)
    -pdf <path>             PDF output directory (default: ./pdf)

    # Direct download mode
    -download               Enable direct download mode
    -doi <string>           DOI(s) to download (comma-separated)
    -input <path>           File containing DOIs (one per line)
    -output <path>          PDF output directory (default: ./pdf)

    -help                   Show help message
    ```

    **Examples**:

    ```bash
    # Archive mode: Download all DOIs with default settings
    ./bin/doihive-darwin-arm64 -a archive

    # Archive mode: Download first 100 DOIs with 4 workers
    ./bin/doihive-darwin-arm64 -a archive -b 100 -w 4

    # Direct download: Single DOI
    ./bin/doihive-darwin-arm64 -download -doi "10.1021/acs.jctc.7b00300" -output pdf

    # Direct download: Multiple DOIs
    ./bin/doihive-darwin-arm64 -download -doi "10.1021/xxx,10.1039/yyy" -output pdf

    # Direct download: From DOI list file (e.g., retry failed DOIs)
    ./bin/doihive-darwin-arm64 -download -input pdf/logs/retry_dois.txt -output pdf

    # For very large batches, you can increase workers (but may risk 403)
    ./bin/doihive-darwin-arm64 -a archive -b 1000 -w 8
    ```

4. **Output**:
    - PDFs are saved to `pdf/` directory (or specified directory)
    - Failed HTML pages saved to `pdf/debug/` for troubleshooting (only for unexpected errors)
    - **Log files** saved to `pdf/logs/`:
      - `download_log_<timestamp>.txt` - Complete download log
      - `failed_dois_<timestamp>.txt` - Detailed failed DOI information
      - `retry_dois_<timestamp>.txt` - DOI-only list for easy retry
    - **Real-time progress bar** showing download progress with live success/skip/failed counts
    - Error information displayed in console
    - Detailed statistics including throughput and average wall-clock time

    **Progress Bar Example**:

    ```shell
    📥 下载中 [✅5 ⏭️0 ❌2] [=========>--------] 7/20 35% 2.3 it/s
    ```

    **Log Files Example**:

    ```shell
    📝 日志文件已保存:
      📄 完整日志: pdf/logs/download_log_2026-01-07_20-22-06.txt
      ❌ 失败详情: pdf/logs/failed_dois_2026-01-07_20-22-06.txt
      🔄 重试列表: pdf/logs/retry_dois_2026-01-07_20-22-06.txt
    ```

### Workflow

1. **DOI Extraction**: The script scans all `.txt` files in `archive/` and extracts DOIs
2. **DOI Validation**: Checks for missing DOIs and provides detailed statistics
3. **URL Construction**: Builds Sci-Hub URLs from extracted DOIs
4. **PDF Download**: Downloads PDFs using multi-threaded requests
5. **Error Handling**: Records failed downloads with detailed error information

### Anti-403 Protection

Both Python and Go implementations include comprehensive protection against 403 errors:

- **Complete browser headers**: Full User-Agent, Accept, Accept-Language, and other headers to mimic real browsers
- **Random delays**: 1.0-4.0 seconds before each request to avoid being flagged as a bot
- **Automatic retry**: Up to 3 retries with exponential backoff when encountering 403 errors
- **Referer headers**: Added for PDF downloads to indicate source page
- **Low concurrency by default**: Default 2-3 workers to minimize risk of triggering rate limits

### DOI Cache (Go)

The Go version maintains two cache files in `pdf/` directory to skip processed DOIs **without any network requests**:

- `downloaded.txt` - Successfully downloaded DOIs
- `not_available.txt` - DOIs confirmed unavailable on Sci-Hub

Benefits:
- **Resume support**: Interrupt and continue anytime
- **Reduced risk**: No repeated requests for known results
- **Persistent**: Cache accumulates across runs

### Safe Harvest Script (Go)

For large-scale downloads, use `scripts/harvest.sh` for gradual, safe batch downloading:

```bash
# Default: 30 DOIs per batch, 60-180s random delay between batches
./scripts/harvest.sh -a ./archive

# Custom: 50 per batch, max 10 rounds, 2-5min delay
./scripts/harvest.sh -a ./archive -b 50 -r 10 -d 120 -D 300
```

Features:
- **Auto-stop**: Stops after 2 consecutive high-error rounds (≥80% errors with <2 successes)
- **Random delays**: Mimics human behavior between batches
- **Real-time output**: Stream progress bar and statistics
- **Graceful exit**: `Ctrl+C` shows summary statistics

**Recommended Settings**:

- **Default (3 workers)**: Safest, ~65-80% success rate, suitable for most use cases
- **4 workers**: Still safe, slightly faster
- **2 workers**: Most conservative, use if experiencing 403 errors

### Performance Comparison

| Version | Concurrency | Throughput (tasks/sec) | Success Rate | Best For |
| --------- | ------------- | ------------------------ | -------------- | ---------- |
| **Go** | 3 (default) | ~2-3 | ~65-80% | All use cases (recommended) |
| **Go** | 4-8 | ~3-5 | ~60-75% | Medium batches with acceptable risk |
| **Python** | 3 (default) | ~1-2 | ~65-80% | Small to medium downloads |

**Recommendations**:

- **< 1000 tasks**: Default settings (3 workers) work well for both versions
- **1000-3000 tasks**: Go version recommended (2-3x faster, same safety)
- **> 3000 tasks**: Go version strongly recommended, consider using 4 workers for better throughput

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

- [x] Extract DOIs from WoS TXT files
- [x] Validate and check DOI completeness
- [x] Construct Sci-Hub URLs from DOIs
- [x] Batch download PDFs with multi-threading (Python)
- [x] High-performance concurrent downloads with goroutines (Go)
- [x] **Anti-403 protection**: Complete browser headers, random delays, retry mechanism
- [x] **CAPTCHA bypass**: Automatic robot verification using headless browser (Go)
- [x] **Gzip decompression**: Automatic handling of compressed HTML/PDF responses
- [x] **Smart error detection**: Identify unavailable articles, captcha pages, etc.
- [x] **Real-time progress bar**: Live progress tracking with statistics (Go)
- [x] **Log persistence**: Download logs, failed DOIs, retry lists (Go)
- [x] **DOI cache**: Skip processed DOIs without network requests (Go)
- [x] **Safe harvest script**: Gradual batch downloading with auto-stop (Go)
- [x] **Direct download mode**: Download from DOI strings or files (Go)
- [x] Error handling and logging
- [x] Beautiful console output with progress tracking (Python)
- [x] Comprehensive statistics and summaries
- [x] HTTP connection pooling for optimal performance
- [x] Configurable concurrency and download limits
- [x] Performance metrics (throughput, average wall-clock time)
- [x] Cross-platform compilation support (Go)
- [x] Debug HTML saving for troubleshooting (only for unexpected errors)

### 🚧 In Progress / Planned

- [ ] Automatic DOI retrieval from search queries
- [ ] Support for other bibliographic data sources (beyond WoS)
- [ ] Configuration file support
- [ ] Multiple Sci-Hub mirror support
- [ ] Distributed processing support

### 🎯 Future Goals

- [ ] End-to-end automation: Search query → DOI retrieval → PDF download
- [ ] Web interface
- [ ] API support
- [ ] Database integration for DOI management

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Disclaimer

This tool is for educational and research purposes only. Please respect copyright laws and publisher terms of service when downloading academic papers.
