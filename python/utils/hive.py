# python/utils/hive.py
# External dependencies / 外部依赖
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn, TimeElapsedColumn
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse
from rich.console import Console
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict, Any
from rich.table import Table
from pathlib import Path
from rich import box
import requests
import json
import time
import re


def pdf_hive(
    urls: list[str], pdf_dir: Path, error_dir: Path = None, max_workers: int = 4
):
    """
    批量下载 PDF 文件（多线程版本）
    Batch download PDF files (multi-threaded)

    Args:
        urls (list[str]): PDF URL 列表 / List of PDF URLs
        pdf_dir (Path): 输出目录 / Output directory
        error_dir (Path): 错误日志目录，如果为 None 则使用 pdf_dir / Error log directory
        max_workers (int): 最大并发线程数 / Maximum number of concurrent threads
    """
    # 确保输出目录存在 / Ensure output directory exists
    pdf_dir.mkdir(parents=True, exist_ok=True)

    # 设置错误日志目录和文件路径 / Set error log directory and file path
    if error_dir is None:
        error_dir = pdf_dir
    else:
        error_dir.mkdir(parents=True, exist_ok=True)

    # 根据时间构造错误日志文件名 / Construct error log filename based on timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    error_log_filename = f"download_errors_{timestamp}.json"
    error_log_path = error_dir / error_log_filename

    # 统计信息 / Statistics
    stats = {
        "total": len(urls),
        "success": 0,
        "skip": 0,
        "failed": 0,
        "errors": [],
        "total_size": 0,  # 总下载大小 / Total download size
        "download_times": [],  # 每个文件的下载时间 / Download time for each file
        "success_times": [],  # 成功下载的时间 / Success download times
    }

    # 创建 Rich 控制台 / Create Rich console
    console = Console()
    
    console.print(f"\n[bold cyan]📚 开始批量下载[/bold cyan] [yellow]共 {stats['total']} 个 URL[/yellow]")
    console.print(f"[bold cyan]🔧 使用[/bold cyan] [yellow]{max_workers} 个并发线程[/yellow]\n")

    # 记录开始时间 / Record start time
    start_time = time.time()

    # 设置请求头，模拟浏览器 / Set request headers to simulate browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    # 创建 Rich 进度条 / Create Rich progress bar
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("•"),
        TextColumn("[green]✅ {task.fields[success]}[/green]"),
        TextColumn("[yellow]⏭️ {task.fields[skip]}[/yellow]"),
        TextColumn("[red]❌ {task.fields[failed]}[/red]"),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("<"),
        TimeRemainingColumn(),
        console=console,
        expand=True,
    )

    # 使用线程池执行下载任务 / Use thread pool to execute download tasks
    with progress:
        task_id = progress.add_task(
            "[cyan]📥 下载进度[/cyan]",
            total=stats["total"],
            success=0,
            skip=0,
            failed=0,
        )

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务并记录开始时间 / Submit all tasks and record start time
            future_to_url = {}
            future_to_start_time = {}
            for url in urls:
                future = executor.submit(_download_single_pdf, url, headers, pdf_dir)
                future_to_url[future] = url
                future_to_start_time[future] = time.time()

            # 处理完成的任务 / Process completed tasks
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                file_start_time = future_to_start_time[future]

                try:
                    result = future.result()
                    file_duration = time.time() - file_start_time
                    stats["download_times"].append(file_duration)

                    if result["status"] == "success":
                        stats["success"] += 1
                        stats["total_size"] += result["size"]
                        stats["success_times"].append(file_duration)  # 记录成功时间
                    elif result["status"] == "skip":
                        stats["skip"] += 1
                    else:  # failed / 失败
                        stats["failed"] += 1
                        error_info = {
                            "url": url,
                            "doi": result.get("doi", ""),
                            "error": result.get("error", "未知错误"),
                            "timestamp": datetime.now().isoformat(),
                        }
                        stats["errors"].append(error_info)

                    # 更新进度条 / Update progress bar
                    progress.update(
                        task_id,
                        advance=1,
                        success=stats["success"],
                        skip=stats["skip"],
                        failed=stats["failed"],
                    )

                except Exception as e:
                    stats["failed"] += 1
                    file_duration = time.time() - file_start_time
                    stats["download_times"].append(file_duration)
                    error_info = {
                        "url": url,
                        "doi": "",
                        "error": f"异常: {str(e)}",
                        "timestamp": datetime.now().isoformat(),
                    }
                    stats["errors"].append(error_info)
                    progress.update(
                        task_id,
                        advance=1,
                        success=stats["success"],
                        skip=stats["skip"],
                        failed=stats["failed"],
                    )

    # 计算总时间和平均时间 / Calculate total time and average time
    total_time = time.time() - start_time
    avg_time = (
        sum(stats["download_times"]) / len(stats["download_times"])
        if stats["download_times"]
        else 0
    )

    # 保存错误日志 / Save error log
    if stats["errors"]:
        with open(error_log_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "summary": {
                        "total_errors": len(stats["errors"]),
                        "generated_at": datetime.now().isoformat(),
                    },
                    "errors": stats["errors"],
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        console.print(f"\n[bold yellow]📝 错误日志已保存到:[/bold yellow] [cyan]{error_log_path}[/cyan]")

    # 格式化文件大小 / Format file size
    def format_size(size_bytes):
        """格式化文件大小 / Format file size"""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"

    # 格式化时间 / Format time
    def format_time(seconds):
        """格式化时间 / Format time"""
        if seconds < 60:
            return f"{seconds:.2f} 秒"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.2f} 分钟"
        else:
            hours = seconds / 3600
            return f"{hours:.2f} 小时"

    # 创建统计表格 / Create statistics table
    table = Table(title="📊 下载汇总统计 / Download Summary Statistics", box=box.ROUNDED)
    table.add_column("项目 / Item", style="cyan", no_wrap=True)
    table.add_column("数值 / Value", style="magenta", justify="right")
    
    table.add_row("📁 总计 / Total", f"{stats['total']:>6} 个文件")
    table.add_row("✅ 成功 / Success", f"[green]{stats['success']:>6}[/green] 个文件")
    table.add_row("⏭️  跳过 / Skipped", f"[yellow]{stats['skip']:>6}[/yellow] 个文件")
    table.add_row("❌ 失败 / Failed", f"[red]{stats['failed']:>6}[/red] 个文件")
    table.add_section()
    
    if stats["total"] > 0:
        success_rate = (stats["success"] / stats["total"]) * 100
        table.add_row("📈 成功率 / Success Rate", f"[green]{success_rate:>5.2f}%[/green]")
    if stats["total_size"] > 0:
        table.add_row("💾 总大小 / Total Size", f"[cyan]{format_size(stats['total_size'])}[/cyan]")
    table.add_section()
    
    table.add_row("⏱️  总耗时 / Total Time", f"[yellow]{format_time(total_time)}[/yellow]")
    if stats["download_times"]:
        table.add_row("⚡ 平均耗时 / Avg Time", f"[yellow]{format_time(avg_time)}[/yellow]")
        if stats["success_times"]:
            avg_success_time = sum(stats["success_times"]) / len(stats["success_times"])
            table.add_row("🚀 成功平均 / Success Avg", f"[green]{format_time(avg_success_time)}[/green]")
    
    console.print()
    console.print(table)

    return stats


def _download_single_pdf(url: str, headers: dict, pdf_dir: Path) -> Dict[str, Any]:
    """
    下载单个 PDF 文件的完整逻辑
    Complete logic for downloading a single PDF file

    Args:
        url (str): Sci-Hub 页面 URL / Sci-Hub page URL
        headers (dict): HTTP 请求头 / HTTP request headers
        pdf_dir (Path): PDF 保存目录 / PDF save directory

    Returns:
        dict: 包含 status, filename, size, doi, error 等字段的字典 /Dictionary containing status, filename, size, doi, error fields
    """
    result = {"status": "failed", "filename": "", "size": 0, "doi": "", "error": ""}

    # 从 URL 中提取 DOI / Extract DOI from URL
    parsed_url = urlparse(url)
    doi = parsed_url.path.lstrip("/")
    result["doi"] = doi

    # 清理 DOI 中的特殊字符，用于文件名 / Clean special characters in DOI for filename
    safe_filename = doi.replace("/", "_").replace(":", "_")
    pdf_filename = f"{safe_filename}.pdf"
    result["filename"] = pdf_filename
    pdf_file_path = pdf_dir / pdf_filename

    # 检查文件是否已存在 / Check if file already exists
    if pdf_file_path.exists():
        result["status"] = "skip"
        result["size"] = pdf_file_path.stat().st_size
        return result

    # 第一步：获取页面 HTML / Step 1: Get page HTML
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        result["error"] = f"页面请求失败: {str(e)}"
        return result

    html_content = response.text
    soup = BeautifulSoup(html_content, "html.parser")

    # 第二步：提取 PDF URL / Step 2: Extract PDF URL
    pdf_url = _extract_pdf_url(html_content, soup, url)

    if not pdf_url:
        result["error"] = "未能从页面中提取 PDF URL"
        return result

    # 第三步：下载 PDF 文件 / Step 3: Download PDF file
    try:
        pdf_response = requests.get(pdf_url, headers=headers, timeout=30, stream=True)
        pdf_response.raise_for_status()

        # 使用 stream=True 下载大文件 / Use stream=True to download large files
        with open(pdf_file_path, "wb") as f:
            for chunk in pdf_response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        # 检查文件大小 / Check file size
        file_size = pdf_file_path.stat().st_size
        if file_size == 0:
            result["error"] = "下载的文件大小为 0"
            pdf_file_path.unlink()
            return result

        # 验证文件是否为有效的 PDF（检查文件头）/ Validate if file is a valid PDF (check file header)
        with open(pdf_file_path, "rb") as f:
            file_header = f.read(4)
            if file_header != b"%PDF":
                result["error"] = "下载的文件不是有效的 PDF 文件"
                pdf_file_path.unlink()
                return result

        result["status"] = "success"
        result["size"] = file_size
        return result

    except requests.exceptions.RequestException as e:
        result["error"] = f"PDF 下载失败: {str(e)}"
        if pdf_file_path.exists():
            pdf_file_path.unlink()
        return result
    except Exception as e:
        result["error"] = f"未知错误: {str(e)}"
        if pdf_file_path.exists():
            pdf_file_path.unlink()
        return result


def _extract_pdf_url(
    html_content: str, soup: BeautifulSoup, base_url: str
) -> str | None:
    """
    从 HTML 中提取 PDF URL
    Extract PDF URL from HTML

    Args:
        html_content (str): HTML 内容字符串 / HTML content string
        soup (BeautifulSoup): BeautifulSoup 解析对象 / BeautifulSoup parsed object
        base_url (str): 基础 URL / Base URL

    Returns:
        str | None: PDF URL 或 None / PDF URL or None
    """
    pdf_url = None

    # 方法1：优先使用 BeautifulSoup 查找下载链接 / Method 1: Use BeautifulSoup to find download link (preferred)
    download_div = soup.find("div", class_="download")
    if download_div:
        a_tag = download_div.find("a")
        if a_tag and a_tag.get("href"):
            download_path = a_tag.get("href")
            pdf_url = urljoin(base_url, download_path)
            return pdf_url

    # 方法2：使用正则表达式提取下载链接（备用方案）/ Method 2: Use regex to extract download link (fallback)
    pattern = r'<div[^>]*class\s*=\s*["\']download["\'][^>]*>.*?<a[^>]+href\s*=\s*["\']([^"\']+)["\']'
    match = re.search(pattern, html_content, re.IGNORECASE | re.DOTALL)
    if match:
        download_path = match.group(1)
        pdf_url = urljoin(base_url, download_path)
        return pdf_url

    # 方法3：如果下载链接不存在，再使用 object 标签（备用方案）/ Method 3: Use object tag if download link not found (fallback)
    object_tag = soup.find("object", type="application/pdf")
    if not object_tag:
        object_tag = soup.find("object", attrs={"data": True})

    if object_tag and object_tag.get("data"):
        pdf_path = object_tag.get("data")
        if "#" in pdf_path:
            pdf_path = pdf_path.split("#")[0]
        pdf_url = urljoin(base_url, pdf_path)
        return pdf_url

    # 方法4：使用正则表达式提取 object 标签的 data 属性（最后备用方案）/ Method 4: Use regex to extract object tag data attribute (last fallback)
    pattern = r'<object[^>]+data\s*=\s*["\']([^"\']+)["\']'
    match = re.search(pattern, html_content, re.IGNORECASE)
    if match:
        pdf_path = match.group(1)
        if "#" in pdf_path:
            pdf_path = pdf_path.split("#")[0]
        pdf_url = urljoin(base_url, pdf_path)
        return pdf_url

    return None
