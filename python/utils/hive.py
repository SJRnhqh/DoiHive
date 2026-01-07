# python/utils/hive.py
# External dependencies / 外部依赖
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeRemainingColumn,
    TimeElapsedColumn,
)
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
import logging
import json
import time
import re
import random


# Local modules / 本地模块
from .logger import log_to_file_only


def pdf_hive(
    urls: list[str], pdf_dir: Path, error_dir: Path = None, max_workers: int = 3
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
    logger = logging.getLogger("doihive")
    console = Console()
    
    info_msg = f"📚 开始批量下载，共 {stats['total']} 个 URL"
    log_to_file_only(logging.INFO, info_msg)
    # 控制台美化输出，不重复日志 / Beautified console output, no duplicate log
    console.print(
        f"\n[bold cyan]📚 开始批量下载[/bold cyan] [yellow]共 {stats['total']} 个 URL[/yellow]"
    )

    worker_msg = f"🔧 使用 {max_workers} 个并发线程"
    log_to_file_only(logging.INFO, worker_msg)
    console.print(
        f"[bold cyan]🔧 使用[/bold cyan] [yellow]{max_workers} 个并发线程[/yellow]\n"
    )

    # 记录开始时间 / Record start time
    start_time = time.time()

    # 创建复用的 Session（连接池优化）/ Create reusable Session (connection pool optimization)
    session = requests.Session()
    # 设置完整的浏览器请求头，避免被识别为爬虫 / Set complete browser headers to avoid being identified as a crawler
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
    })
    # 配置连接池 / Configure connection pool
    adapter = requests.adapters.HTTPAdapter(
        pool_connections=max_workers * 2,  # 最大连接池数 / Max connection pools
        pool_maxsize=max_workers * 2,      # 每个池的最大连接数 / Max connections per pool
        max_retries=0,                     # 禁用重试（由外部处理错误）/ Disable retries (handle errors externally)
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)

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
                future = executor.submit(_download_single_pdf, url, session, pdf_dir)
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
        error_log_msg = f"📝 错误日志已保存到: {error_log_path}"
        log_to_file_only(logging.WARNING, error_log_msg)

        # 记录所有错误到日志文件 / Log all errors to file
        for error in stats["errors"]:
            log_to_file_only(
                logging.ERROR,
                f"下载失败 - DOI: {error.get('doi', 'N/A')}, URL: {error.get('url', 'N/A')}, 错误: {error.get('error', 'N/A')}",
            )

        # 控制台用 Rich 表格展示错误 / Display errors in Rich table on console
        console.print(
            f"\n[bold yellow]📝 错误日志已保存到:[/bold yellow] [cyan]{error_log_path}[/cyan]"
        )

        # 按错误类型分组统计 / Group errors by error type
        error_groups = {}
        for error in stats["errors"]:
            error_msg = error.get("error", "未知错误")
            # 提取错误类型（去除动态部分）/ Extract error type (remove dynamic parts)
            error_type = error_msg
            # 对于包含冒号的错误，提取前缀作为类型 / For errors with colons, extract prefix as type
            if ":" in error_msg:
                error_type = error_msg.split(":", 1)[0]
            
            if error_type not in error_groups:
                error_groups[error_type] = []
            error_groups[error_type].append(error)

        # 创建错误汇总表格 / Create error summary table
        error_table = Table(
            title=f"❌ 下载失败汇总 / Download Error Summary ({len(stats['errors'])} 个错误，{len(error_groups)} 种类型)",
            box=box.ROUNDED,
        )
        error_table.add_column(
            "错误类型", style="red", no_wrap=False, width=40
        )
        error_table.add_column(
            "数量", style="yellow", justify="right", width=8, no_wrap=True
        )
        error_table.add_column(
            "示例 DOI", style="cyan", no_wrap=False, width=35
        )

        # 按数量降序排序 / Sort by count in descending order
        sorted_groups = sorted(
            error_groups.items(), key=lambda x: len(x[1]), reverse=True
        )

        for error_type, errors in sorted_groups:
            count = len(errors)
            # 收集示例 DOI（最多3个）/ Collect example DOIs (max 3)
            example_dois = []
            for error in errors[:3]:
                doi = error.get("doi", "N/A")
                if len(doi) > 30:
                    doi = doi[:27] + "..."
                example_dois.append(doi)
            
            example_str = ", ".join(example_dois)
            if count > 3:
                example_str += f" ... (共 {count} 个)"
            
            error_table.add_row(error_type, str(count), example_str)

        console.print()
        console.print(error_table)

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
    table = Table(
        title="📊 下载汇总统计 / Download Summary Statistics", box=box.ROUNDED
    )
    table.add_column("项目 / Item", style="cyan", no_wrap=True)
    table.add_column("数值 / Value", style="magenta", justify="right")

    table.add_row("📁 总计 / Total", f"{stats['total']:>6} 个文件")
    table.add_row("✅ 成功 / Success", f"[green]{stats['success']:>6}[/green] 个文件")
    table.add_row("⏭️  跳过 / Skipped", f"[yellow]{stats['skip']:>6}[/yellow] 个文件")
    table.add_row("❌ 失败 / Failed", f"[red]{stats['failed']:>6}[/red] 个文件")
    table.add_section()

    if stats["total"] > 0:
        success_rate = (stats["success"] / stats["total"]) * 100
        table.add_row(
            "📈 成功率 / Success Rate", f"[green]{success_rate:>5.2f}%[/green]"
        )
    if stats["total_size"] > 0:
        table.add_row(
            "💾 总大小 / Total Size", f"[cyan]{format_size(stats['total_size'])}[/cyan]"
        )
    table.add_section()

    table.add_row(
        "⏱️  总耗时 / Total Time", f"[yellow]{format_time(total_time)}[/yellow]"
    )
    # 计算平均墙钟时间（总耗时 / 总任务数）/ Calculate average wall-clock time (total time / total tasks)
    if stats["total"] > 0 and total_time > 0:
        avg_wall_clock_time = total_time / stats["total"]
        table.add_row(
            "📊 平均墙钟时间 / Avg Wall-clock Time",
            f"[cyan]{format_time(avg_wall_clock_time)}/任务[/cyan]",
        )
    if stats["download_times"]:
        table.add_row(
            "⚡ 平均耗时 / Avg Time", f"[yellow]{format_time(avg_time)}[/yellow]"
        )
        if stats["success_times"]:
            avg_success_time = sum(stats["success_times"]) / len(stats["success_times"])
            table.add_row(
                "🚀 成功平均 / Success Avg",
                f"[green]{format_time(avg_success_time)}[/green]",
            )

    # 记录统计信息到日志（只写入文件，不显示在控制台，避免与表格重复） / Log statistics to file only (not shown in console to avoid duplication with table)
    log_to_file_only(logging.INFO, "=" * 70)
    log_to_file_only(logging.INFO, "📊 下载汇总统计:")
    log_to_file_only(logging.INFO, f"📁 总计: {stats['total']} 个文件")
    log_to_file_only(logging.INFO, f"✅ 成功: {stats['success']} 个文件")
    log_to_file_only(logging.INFO, f"⏭️  跳过: {stats['skip']} 个文件")
    log_to_file_only(logging.INFO, f"❌ 失败: {stats['failed']} 个文件")
    if stats["total"] > 0:
        success_rate = (stats["success"] / stats["total"]) * 100
        log_to_file_only(logging.INFO, f"📈 成功率: {success_rate:.2f}%")
    if stats["total_size"] > 0:
        log_to_file_only(logging.INFO, f"💾 总大小: {format_size(stats['total_size'])}")
    log_to_file_only(logging.INFO, f"⏱️  总耗时: {format_time(total_time)}")
    if stats["total"] > 0 and total_time > 0:
        avg_wall_clock_time = total_time / stats["total"]
        log_to_file_only(
            logging.INFO, f"📊 平均墙钟时间: {format_time(avg_wall_clock_time)}/任务"
        )
    if stats["download_times"]:
        log_to_file_only(logging.INFO, f"⚡ 平均耗时: {format_time(avg_time)}")
        if stats["success_times"]:
            avg_success_time = sum(stats["success_times"]) / len(stats["success_times"])
            log_to_file_only(
                logging.INFO, f"🚀 成功平均: {format_time(avg_success_time)}"
            )
    log_to_file_only(logging.INFO, "=" * 70)

    # 控制台只显示表格，不显示日志 / Console only shows table, no log output
    console.print()
    console.print(table)

    return stats


def _download_single_pdf(url: str, session: requests.Session, pdf_dir: Path) -> Dict[str, Any]:
    """
    下载单个 PDF 文件的完整逻辑
    Complete logic for downloading a single PDF file

    Args:
        url (str): Sci-Hub 页面 URL / Sci-Hub page URL
        session (requests.Session): 复用的 HTTP Session（连接池）/ Reusable HTTP Session (connection pool)
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
    # 添加随机延迟，避免请求过快被识别为爬虫 / Add random delay to avoid being identified as a crawler
    time.sleep(random.uniform(0.5, 2.0))
    
    # 重试机制：最多重试 3 次 / Retry mechanism: up to 3 retries
    max_retries = 3
    retry_delay = 2  # 初始重试延迟（秒）/ Initial retry delay (seconds)
    
    for attempt in range(max_retries):
        try:
            response = session.get(url, timeout=10)
            
            # 如果是 403 错误，等待后重试 / If 403 error, wait and retry
            if response.status_code == 403:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (attempt + 1) + random.uniform(0, 2)
                    time.sleep(wait_time)
                    continue
                else:
                    result["error"] = f"页面请求失败: HTTP 403 (已重试 {max_retries} 次)"
                    return result
            
            response.raise_for_status()
            break  # 成功，退出重试循环 / Success, exit retry loop
            
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = retry_delay * (attempt + 1) + random.uniform(0, 2)
                time.sleep(wait_time)
                continue
            else:
                result["error"] = f"页面请求失败: {str(e)} (已重试 {max_retries} 次)"
                return result
    else:
        # 所有重试都失败了 / All retries failed
        result["error"] = f"页面请求失败: 已重试 {max_retries} 次"
        return result

    html_content = response.text
    soup = BeautifulSoup(html_content, "html.parser")

    # 第二步：提取 PDF URL / Step 2: Extract PDF URL
    pdf_url = _extract_pdf_url(html_content, soup, url)

    if not pdf_url:
        result["error"] = "未能从页面中提取 PDF URL"
        return result

    # 第三步：下载 PDF 文件 / Step 3: Download PDF file
    # 添加随机延迟 / Add random delay
    time.sleep(random.uniform(0.3, 1.0))
    
    # 为 PDF 下载添加 Referer 头 / Add Referer header for PDF download
    headers_for_pdf = {"Referer": url}
    
    # 重试机制：最多重试 3 次 / Retry mechanism: up to 3 retries
    for attempt in range(max_retries):
        try:
            pdf_response = session.get(pdf_url, timeout=30, stream=True, headers=headers_for_pdf)
            
            # 如果是 403 错误，等待后重试 / If 403 error, wait and retry
            if pdf_response.status_code == 403:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (attempt + 1) + random.uniform(0, 2)
                    time.sleep(wait_time)
                    continue
                else:
                    result["error"] = f"PDF 下载失败: HTTP 403 (已重试 {max_retries} 次)"
                    return result
            
            pdf_response.raise_for_status()
            break  # 成功，退出重试循环 / Success, exit retry loop
            
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait_time = retry_delay * (attempt + 1) + random.uniform(0, 2)
                time.sleep(wait_time)
                continue
            else:
                result["error"] = f"PDF 下载失败: {str(e)} (已重试 {max_retries} 次)"
                if pdf_file_path.exists():
                    pdf_file_path.unlink()
                return result
    else:
        # 所有重试都失败了 / All retries failed
        result["error"] = f"PDF 下载失败: 已重试 {max_retries} 次"
        if pdf_file_path.exists():
            pdf_file_path.unlink()
        return result

    # 使用 stream=True 下载大文件 / Use stream=True to download large files
    try:
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

    except Exception as e:
        result["error"] = f"文件写入失败: {str(e)}"
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
