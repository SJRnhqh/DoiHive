# python/utils/analyze.py
# External dependencies / 外部依赖
from pathlib import Path
import re


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
    if not archive_dir.exists():
        print(f"❌ 目录不存在: {archive_dir.resolve()}")
        return

    # 获取所有 .txt 文件并排序 / Get all .txt files and sort them
    txt_files = sorted([f for f in archive_dir.glob("*.txt")])
    if not txt_files:
        print(f"📭 {archive_dir} 下没有 .txt 文件")
        return

    print(f"🔍 发现 {len(txt_files)} 个 .txt 文件，开始批量分析...\n")

    all_stats = []
    grand_total_records = 0
    grand_total_dois = 0
    grand_missing = 0
    all_dois = []  # 收集所有 DOI 用于去重统计 / Collect all DOIs for unique count
    doi_file_map = (
        {}
    )  # 追踪每个 DOI 出现的文件和次数 / Track which files each DOI appears in and count

    # 处理每个文件 / Process each file
    for file_path in txt_files:
        print(f"📄 处理文件: {file_path.name}")
        stats = _analyze_file(file_path)
        if stats is None:
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

        # 如果该文件有缺失，打印详情 / If this file has missing DOIs, print details
        if stats["missing_count"] > 0:
            print(f"   ❌ {stats['missing_count']} 条记录缺失 DOI")
            for idx, content in stats["missing_details"]:
                print(f"\n   --- {file_path.name} | 无 DOI 记录 #{idx} ---")
                # 缩进内容以便阅读 / Indent content for readability
                print(f"   {content.replace(chr(10), chr(10) + '   ')}")
        else:
            print(f"   ✅ 全部 {stats['total_records']} 条记录均有 DOI")

        print()  # 空行分隔 / Empty line separator

    # === 最终汇总 / Final Summary ===
    unique_dois = len(set(all_dois))  # 唯一 DOI 数量 / Unique DOI count
    print("=" * 60)
    print("📊 批量分析汇总:")
    print(f"📁 文件总数: {len(txt_files)}")
    print(f"📚 总文献记录数: {grand_total_records}")
    print(f"✅ 总有效 DOI 数（含重复）: {grand_total_dois}")
    print(f"🔑 唯一 DOI 数: {unique_dois}")
    print(f"❌ 总缺失 DOI 数: {grand_missing}")
    if grand_total_records > 0:
        coverage = grand_total_dois / grand_total_records * 100
        print(f"📈 DOI 覆盖率: {coverage:.2f}%")

    # 检查并打印重复 DOI 详情 / Check and print duplicate DOI details
    if grand_total_dois > unique_dois:
        duplicates = grand_total_dois - unique_dois
        print(f"\n🔄 发现 {duplicates} 个重复 DOI:")
        # 找出有重复的 DOI（跨文件重复或同一文件内重复）/ Find DOIs with duplicates (across files or within same file)
        duplicate_dois = {
            doi: file_counts
            for doi, file_counts in doi_file_map.items()
            if sum(file_counts.values()) > 1  # 总出现次数 > 1
        }
        for doi, file_counts in sorted(duplicate_dois.items()):
            total_count = sum(file_counts.values())
            file_list = []
            for filename, count in sorted(file_counts.items()):
                if count > 1:
                    file_list.append(f"{filename} (出现 {count} 次)")
                else:
                    file_list.append(filename)
            print(f"   📄 {doi}")
            if len(file_counts) > 1:
                print(
                    f"      跨 {len(file_counts)} 个文件，共出现 {total_count} 次: {', '.join(file_list)}"
                )
            else:
                print(
                    f"      在同一文件中出现 {total_count} 次: {', '.join(file_list)}"
                )

    print("=" * 60)


def doi_extractor(archive_dir: Path) -> list[str]:
    """
    从 archive 目录提取所有有效的 DOI
    Extract all valid DOIs from archive directory

    Args:
        archive_dir (Path): archive 目录路径 / Archive directory path

    Returns:
        list[str]: DOI 列表（已去重）/ List of unique DOIs
    """
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

    unique_dois = list(set(dois))  # 去重 / Remove duplicates
    print(f"🔍 发现 {len(unique_dois)} 个有效 DOI")
    return unique_dois
