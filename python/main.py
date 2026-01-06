# python/main.py
# External dependencies / 外部依赖
from pathlib import Path
import logging


# Local modules / 本地模块
from utils import setup_logger, log_to_file_only, doi_checker, doi_extractor, pdf_hive


def main():
    """
    主函数：检查 archive 目录下的所有文件中的 DOI 记录
    Main function: Check DOI records in all files under archive directory
    """
    # 初始化日志 / Initialize logger
    logs_dir = Path("../logs")
    _ = setup_logger(logs_dir=logs_dir)

    # 使用 Rich Console 美化启动信息 / Use Rich Console to beautify startup message
    from rich.console import Console
    from rich.panel import Panel

    console = Console()

    console.print()
    console.print(
        Panel(
            "[bold cyan]🚀 DoiHive 开始运行 / DoiHive Started[/bold cyan]",
            border_style="cyan",
            expand=False,
        )
    )
    console.print()

    # 记录到日志（只写入文件，控制台已有 Panel 显示） / Log to file only (console already shows Panel)
    log_to_file_only(logging.INFO, "=" * 70)
    log_to_file_only(logging.INFO, "🚀 DoiHive 开始运行 / DoiHive Started")
    log_to_file_only(logging.INFO, "=" * 70)

    # 获取 archive 目录路径 / Get archive directory path
    archive_dir = Path("../archive")

    # 检查 DOI 记录 / Check DOI records
    doi_checker(archive_dir)

    # 提取所有有效的 DOI / Extract all valid DOIs
    dois = doi_extractor(archive_dir)

    # 设置Sci-hub URL / Set Sci-hub URL
    sci_hub_url = "https://sci-hub.se"

    # DOI 列表批量构造为 URL / Construct URLs from DOI list
    urls = [f"{sci_hub_url}/{doi}" for doi in dois]

    # 获取 pdf 目录路径 / Get pdf directory path
    pdf_dir = Path("../pdf")

    # 获取 error 目录路径 / Get error directory path
    error_dir = Path("../error")

    # 批量下载 PDF / Batch download PDFs
    pdf_hive(urls[:10], pdf_dir, error_dir)

    # 使用 Rich Console 美化完成信息 / Use Rich Console to beautify completion message
    console.print()
    console.print(
        Panel(
            "[bold green]✅ DoiHive 运行完成 / DoiHive Completed[/bold green]",
            border_style="green",
            expand=False,
        )
    )
    console.print()

    # 记录到日志（只写入文件，控制台已有 Panel 显示） / Log to file only (console already shows Panel)
    log_to_file_only(logging.INFO, "=" * 70)
    log_to_file_only(logging.INFO, "✅ DoiHive 运行完成 / DoiHive Completed")
    log_to_file_only(logging.INFO, "=" * 70)


if __name__ == "__main__":
    main()
