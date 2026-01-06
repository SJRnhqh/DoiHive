# python/main.py
# External dependencies / 外部依赖
from pathlib import Path


# Local modules / 本地模块
from utils import doi_checker, doi_extractor, pdf_hive


def main():
    """
    主函数：检查 archive 目录下的所有文件中的 DOI 记录
    Main function: Check DOI records in all files under archive directory
    """
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

    # 批量下载 PDF / Batch download PDFs
    # pdf_hive(urls[:3], pdf_dir) TODO: 需要测试
    
    print(urls[:3])


if __name__ == "__main__":
    main()
