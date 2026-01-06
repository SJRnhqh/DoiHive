# python/utils/analyze.py
# External dependencies / 外部依赖
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from pathlib import Path
from rich import box
import logging
import re


# Local modules / 本地模块
from .logger import log_to_file_only


def _parse_wos_records_with_index(text: str):
    """
    解析 WoS 记录文本，返回带索引的记录列表
    Parse WoS record text and return a list of records with indices

    Args:
        text (str): WoS 格式的文本内容 / WoS formatted text content

    Returns:
        list: 包含 (索引, 行列表) 元组的记录列表 / List of records as (index, lines) tuples
    """
    records = []
    raw_blocks = text.strip().split("\nER\n")

    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue
        if block == "EF" or (block.startswith("EF") and len(block.split()) == 1):
            continue

        lines = block.splitlines()
        lines.append("ER")
        records.append((len(records) + 1, lines))

    return records


def _extract_doi_from_record(lines):
    """
    从记录行中提取 DOI
    Extract DOI from record lines

    Args:
        lines (list): 记录的行列表 / List of record lines

    Returns:
        str or None: 提取到的 DOI，如果未找到则返回 None / Extracted DOI or None if not found
    """
    for line in lines:
        if line.startswith("DI"):
            parts = line.split(maxsplit=1)
            if len(parts) == 2:
                doi = parts[1].strip()
                # 验证 DOI 格式 / Validate DOI format
                if re.match(r"^10\.\d{4,9}/[^\s]+$", doi):
                    return doi
    return None


def _read_file_text(file_path: Path) -> str | None:
    """
    读取文件内容，自动处理编码问题
    Read file content with automatic encoding handling

    Args:
        file_path (Path): 文件路径 / File path

    Returns:
        str or None: 文件内容，读取失败时返回 None / File content or None if read fails
    """
    # 尝试使用 UTF-8-SIG 编码读取 / Try reading with UTF-8-SIG encoding
    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            return f.read()
    except UnicodeDecodeError:
        # 如果失败，尝试使用 latin1 编码 / If failed, try latin1 encoding
        try:
            with open(file_path, "r", encoding="latin1") as f:
                return f.read()
        except Exception as e:
            print(f"⚠️ 无法读取 {file_path.name}: {e}")
            return None


def _analyze_file(file_path: Path):
    """
    分析单个 WoS txt 文件，返回统计信息
    Analyze a single WoS txt file and return statistics

    Args:
        file_path (Path): 文件路径 / File path

    Returns:
        dict or None: 包含统计信息的字典，读取失败时返回 None
                    Dictionary containing statistics, or None if read fails
    """
    text = _read_file_text(file_path)
    if text is None:
        return None

    records = _parse_wos_records_with_index(text)
    total = len(records)

    valid_dois = []
    missing_records = []

    # 遍历所有记录，提取 DOI / Iterate through all records to extract DOIs
    for idx, lines in records:
        doi = _extract_doi_from_record(lines)
        if doi:
            valid_dois.append(doi)
        else:
            missing_records.append((idx, "\n".join(lines)))

    return {
        "file": file_path.name,
        "total_records": total,
        "valid_dois": len(valid_dois),
        "missing_count": len(missing_records),
        "missing_details": missing_records,
    }


def doi_checker(archive_dir: Path):
    """
    从 archive 目录加载所有 DOI 记录，检查缺失情况
    Load all DOI records from archive directory and check for missing ones

    Args:
        archive_dir (Path): archive 目录路径 / Archive directory path
    """
    logger = logging.getLogger("doihive")
    console = Console()

    if not archive_dir.exists():
        error_msg = f"❌ 目录不存在: {archive_dir.resolve()}"
        log_to_file_only(logging.ERROR, error_msg)
        console.print(f"[bold red]{error_msg}[/bold red]")
        return

    # 获取所有 .txt 文件并排序 / Get all .txt files and sort them
    txt_files = sorted([f for f in archive_dir.glob("*.txt")])
    if not txt_files:
        warn_msg = f"📭 {archive_dir} 下没有 .txt 文件"
        log_to_file_only(logging.WARNING, warn_msg)
        console.print(f"[yellow]{warn_msg}[/yellow]")
        return

    info_msg = f"🔍 发现 {len(txt_files)} 个 .txt 文件，开始批量分析..."
    log_to_file_only(logging.INFO, info_msg)
    # 控制台美化输出，不重复日志 / Beautified console output, no duplicate log
    console.print(
        f"\n[bold cyan]🔍 发现[/bold cyan] [yellow]{len(txt_files)} 个 .txt 文件[/yellow]，[bold cyan]开始批量分析...[/bold cyan]\n"
    )

    all_stats = []
    grand_total_records = 0
    grand_total_dois = 0
    grand_missing = 0
    all_dois = []  # 收集所有 DOI 用于去重统计 / Collect all DOIs for unique count
    doi_file_map = (
        {}
    )  # 追踪每个 DOI 出现的文件和次数 / Track which files each DOI appears in and count

    # 处理每个文件 / Process each file
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]✅ 处理文件[/cyan]", total=len(txt_files))

        for file_path in txt_files:
            stats = _analyze_file(file_path)
            if stats is None:
                progress.update(task, advance=1)
                continue

            all_stats.append(stats)
            grand_total_records += stats["total_records"]
            grand_total_dois += stats["valid_dois"]
            grand_missing += stats["missing_count"]

            # 收集该文件的所有 DOI 并记录文件信息 / Collect all DOIs from this file and track file info
            text = _read_file_text(file_path)
            if text:
                records = _parse_wos_records_with_index(text)
                for idx, lines in records:
                    doi = _extract_doi_from_record(lines)
                    if doi:
                        all_dois.append(doi)
                        # 记录 DOI 出现的文件和次数 / Record which file this DOI appears in and count
                        if doi not in doi_file_map:
                            doi_file_map[doi] = {}
                        # 统计每个文件中出现的次数 / Count occurrences in each file
                        if file_path.name not in doi_file_map[doi]:
                            doi_file_map[doi][file_path.name] = 0
                        doi_file_map[doi][file_path.name] += 1

            # 更新进度条 / Update progress bar
            progress.update(task, advance=1)
            
            # 显示该文件的基本信息（无论是否有缺失）/ Display this file's basic info (whether missing or not)
            progress.print()  # 空行分隔 / Empty line separator
            
            # 显示文件信息和累计总数 / Display file info and cumulative total
            file_info_msg = f"📄 {file_path.name}: {stats['total_records']} 条记录 (累计: {grand_total_records} 条)"
            progress.print(f"[cyan]{file_info_msg}[/cyan]")
            
            # 如果该文件有缺失，打印详情 / If this file has missing DOIs, print details
            if stats["missing_count"] > 0:
                error_msg = f"   ❌ {stats['missing_count']} 条记录缺失 DOI"
                log_to_file_only(logging.WARNING, error_msg)
                for idx, content in stats["missing_details"]:
                    panel = Panel(
                        content,
                        title=f"[yellow]{file_path.name}[/yellow] | [red]无 DOI 记录 #{idx}[/red]",
                        border_style="red",
                        expand=False,
                    )
                    # 格式化多行内容，每行添加缩进 / Format multi-line content with indentation
                    formatted_content = "\n".join(
                        f"    {line}" for line in content.split("\n")
                    )
                    log_to_file_only(
                        logging.WARNING,
                        f"无 DOI 记录: {file_path.name} #{idx}\n{formatted_content}",
                    )
                    progress.print(panel)
            else:
                success_msg = f"   ✅ 全部 {stats['total_records']} 条记录均有 DOI"
                log_to_file_only(logging.INFO, success_msg)
            
            # 空一行分隔 / Empty line separator
            progress.print()

    # === 最终汇总 / Final Summary ===
    unique_dois = len(set(all_dois))  # 唯一 DOI 数量 / Unique DOI count

    # 创建汇总表格 / Create summary table
    summary_table = Table(
        title="📊 批量分析汇总 / Batch Analysis Summary", box=box.ROUNDED
    )
    summary_table.add_column("项目 / Item", style="cyan", no_wrap=True)
    summary_table.add_column("数值 / Value", style="magenta", justify="right")

    summary_table.add_row("📁 文件总数 / Total Files", f"{len(txt_files)}")
    summary_table.add_row("📚 总文献记录数 / Total Records", f"{grand_total_records}")
    summary_table.add_row(
        "✅ 总有效 DOI 数（含重复）/ Total DOIs (with duplicates)",
        f"{grand_total_dois}",
    )
    summary_table.add_row(
        "🔑 唯一 DOI 数 / Unique DOIs", f"[green]{unique_dois}[/green]"
    )
    summary_table.add_row(
        "❌ 总缺失 DOI 数 / Missing DOIs", f"[red]{grand_missing}[/red]"
    )

    if grand_total_records > 0:
        coverage = grand_total_dois / grand_total_records * 100
        coverage_color = (
            "green" if coverage >= 95 else "yellow" if coverage >= 80 else "red"
        )
        summary_table.add_row(
            "📈 DOI 覆盖率 / DOI Coverage",
            f"[{coverage_color}]{coverage:.2f}%[/{coverage_color}]",
        )

    # 记录汇总信息到日志（只写入文件，不显示在控制台，避免与表格重复） / Log summary to file only (not shown in console to avoid duplication with table)
    log_to_file_only(logging.INFO, "=" * 70)
    log_to_file_only(logging.INFO, "📊 批量分析汇总:")
    log_to_file_only(logging.INFO, f"📁 文件总数: {len(txt_files)}")
    log_to_file_only(logging.INFO, f"📚 总文献记录数: {grand_total_records}")
    log_to_file_only(logging.INFO, f"✅ 总有效 DOI 数（含重复）: {grand_total_dois}")
    log_to_file_only(logging.INFO, f"🔑 唯一 DOI 数: {unique_dois}")
    log_to_file_only(logging.INFO, f"❌ 总缺失 DOI 数: {grand_missing}")
    if grand_total_records > 0:
        coverage = grand_total_dois / grand_total_records * 100
        log_to_file_only(logging.INFO, f"📈 DOI 覆盖率: {coverage:.2f}%")
    log_to_file_only(logging.INFO, "=" * 70)

    # 控制台只显示表格，不显示日志 / Console only shows table, no log output
    console.print()
    console.print(summary_table)

    # 检查并打印重复 DOI 详情 / Check and print duplicate DOI details
    if grand_total_dois > unique_dois:
        duplicates = grand_total_dois - unique_dois
        dup_msg = f"🔄 发现 {duplicates} 个重复 DOI:"
        log_to_file_only(logging.INFO, dup_msg)
        # 控制台美化输出 / Beautified console output
        console.print(f"\n[bold yellow]{dup_msg}[/bold yellow]")

        # 找出有重复的 DOI（跨文件重复或同一文件内重复）/ Find DOIs with duplicates (across files or within same file)
        duplicate_dois = {
            doi: file_counts
            for doi, file_counts in doi_file_map.items()
            if sum(file_counts.values()) > 1  # 总出现次数 > 1
        }

        # 创建重复 DOI 表格 / Create duplicate DOI table
        dup_table = Table(box=box.SIMPLE)
        dup_table.add_column("DOI", style="cyan")
        dup_table.add_column("详情 / Details", style="yellow")

        for doi, file_counts in sorted(duplicate_dois.items()):
            total_count = sum(file_counts.values())
            file_list = []
            for filename, count in sorted(file_counts.items()):
                if count > 1:
                    file_list.append(f"{filename} ([red]出现 {count} 次[/red])")
                else:
                    file_list.append(filename)

            if len(file_counts) > 1:
                details = f"跨 [cyan]{len(file_counts)}[/cyan] 个文件，共出现 [red]{total_count}[/red] 次: {', '.join(file_list)}"
            else:
                details = f"在同一文件中出现 [red]{total_count}[/red] 次: {', '.join(file_list)}"

            dup_table.add_row(f"[bold]{doi}[/bold]", details)
            # 移除 Rich 标记后只记录到文件 / Remove Rich markup and log to file only
            clean_details = (
                details.replace("[red]", "")
                .replace("[/red]", "")
                .replace("[cyan]", "")
                .replace("[/cyan]", "")
            )
            log_to_file_only(logging.INFO, f"重复 DOI: {doi} - {clean_details}")

        # 控制台只显示表格，不显示日志 / Console only shows table, no log output
        console.print(dup_table)


def doi_extractor(archive_dir: Path) -> list[str]:
    """
    从 archive 目录提取所有有效的 DOI
    Extract all valid DOIs from archive directory

    Args:
        archive_dir (Path): archive 目录路径 / Archive directory path

    Returns:
        list[str]: DOI 列表（已去重）/ List of unique DOIs
    """
    console = Console()

    if not archive_dir.exists():
        return []

    dois = []
    txt_files = sorted([f for f in archive_dir.glob("*.txt")])

    # 复用已有的解析函数 / Reuse existing parsing functions
    for file_path in txt_files:
        text = _read_file_text(file_path)
        if text is None:
            continue

        records = _parse_wos_records_with_index(text)
        for idx, lines in records:
            doi = _extract_doi_from_record(lines)
            if doi:
                dois.append(doi)

    # 去重（不保持顺序，提升性能）/ Remove duplicates (order not preserved for performance)
    unique_dois = list(set(dois))

    info_msg = f"🔍 发现 {len(unique_dois)} 个有效 DOI"
    logger = logging.getLogger("doihive")
    log_to_file_only(logging.INFO, info_msg)
    # 控制台美化输出，不重复日志 / Beautified console output, no duplicate log
    console = Console()
    console.print(f"[bold cyan]{info_msg}[/bold cyan]")
    return unique_dois
