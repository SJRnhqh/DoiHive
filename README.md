# DoiHive

A cross-language (Python/Go) tool for batch downloading academic PDFs from DOIs. Currently supports extracting DOIs from Web of Science (WoS) exported TXT files and downloading PDFs via Sci-Hub.

[中文文档](README_zh.md) | [English](README.md)

## Overview

DoiHive automates the process of extracting DOIs from bibliographic data files and downloading corresponding PDFs. The project aims to eventually support automatic DOI retrieval from search queries, but currently focuses on processing existing DOI data.

**Current Status**: Python implementation is complete. Go implementation is planned.

## Features

- ✅ Extract DOIs from WoS exported TXT files
- ✅ Batch download PDFs from Sci-Hub
- ✅ Multi-threaded downloads for improved performance
- ✅ Comprehensive error logging and reporting
- ✅ Beautiful console output with progress tracking
- ✅ Detailed statistics and summaries

## Tech Stack

### Python (Current)

![Python](https://img.shields.io/badge/Python-3.13+-blue?logo=python&logoColor=white)

- **Python 3.13+**
- `beautifulsoup4` - HTML parsing for PDF URL extraction
- `requests` - HTTP requests for downloading
- `rich` - Beautiful terminal output and progress bars

### Go (Planned)

- Go implementation for improved performance

## Installation

### Prerequisites

- Python 3.13 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Setup

1. Clone the repository:

    ```bash
    git clone https://github.com/SJRnhqh/DoiHive.git
    cd DoiHive
    ```

2. Install dependencies using uv:

    ```bash
    uv sync
    ```

    Or using pip:

    ```bash
    pip install -e .
    ```

## Usage

### Current Implementation (Python)

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

### Workflow

1. **DOI Extraction**: The script scans all `.txt` files in `archive/` and extracts DOIs
2. **DOI Validation**: Checks for missing DOIs and provides detailed statistics
3. **URL Construction**: Builds Sci-Hub URLs from extracted DOIs
4. **PDF Download**: Downloads PDFs using multi-threaded requests
5. **Error Handling**: Records failed downloads with detailed error information

### Configuration

You can modify the following in `python/main.py`:

- Number of URLs to process (currently limited to 10 for testing: `urls[:10]`)
- Sci-Hub base URL (default: `https://sci-hub.se`)
- Output directories (`pdf/`, `error/`, `logs/`)

## Project Structure

```txt
DoiHive/
├── python/                 # Python implementation
│   ├── main.py            # Main entry point
│   └── utils/             # Utility modules
│       ├── analyze.py     # DOI extraction and validation
│       ├── hive.py        # PDF download logic
│       └── logger.py      # Logging configuration
├── cmd/                   # Go implementation (planned)
│   └── main.go
├── archive/               # Input: WoS TXT files
├── pyproject.toml         # Python dependencies
└── go.mod                 # Go dependencies (planned)
```

## Development Roadmap

### ✅ Completed

- [x] Extract DOIs from WoS TXT files
- [x] Validate and check DOI completeness
- [x] Construct Sci-Hub URLs from DOIs
- [x] Batch download PDFs with multi-threading
- [x] Error handling and logging
- [x] Beautiful console output with progress tracking
- [x] Comprehensive statistics and summaries

### 🚧 In Progress / Planned

- [ ] Go implementation
- [ ] Automatic DOI retrieval from search queries
- [ ] Support for other bibliographic data sources (beyond WoS)
- [ ] Configuration file support
- [ ] Resume interrupted downloads
- [ ] Rate limiting and retry mechanisms
- [ ] Multiple Sci-Hub mirror support

### 🎯 Future Goals

- [ ] End-to-end automation: Search query → DOI retrieval → PDF download
- [ ] Web interface
- [ ] API support
- [ ] Database integration for DOI management

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Disclaimer

This tool is for educational and research purposes only. Please respect copyright laws and publisher terms of service when downloading academic papers.
