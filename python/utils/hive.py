# python/utils/hive.py
# External dependencies / 外部依赖
import re
import time
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse
import requests


def pdf_hive(urls: list[str], pdf_dir: Path):
    """
    批量下载 PDF 文件
    Batch download PDF files

    Args:
        urls (list[str]): PDF URL 列表 / List of PDF URLs
        pdf_dir (Path): 输出目录 / Output directory
    """
    pdf_dir.mkdir(parents=True, exist_ok=True)

    stats = {"total": len(urls), "success": 0, "failed": 0, "skipped": 0}

    print(f"📥 开始批量下载 {len(urls)} 个 PDF...\n")

    for i, url in enumerate(urls, 1):
        # 从 URL 提取 DOI 作为文件名 / Extract DOI from URL as filename
        doi = url.split("/")[-1]
        filename = unquote(doi).replace("/", "_").replace(":", "_")[:200]
        output_path = pdf_dir / f"{filename}.pdf"

        # 跳过已存在的文件 / Skip existing files
        if output_path.exists():
            print(f"[{i}/{len(urls)}] ⏭️  跳过（已存在）: {doi}")
            stats["skipped"] += 1
            continue

        print(f"[{i}/{len(urls)}] 📄 下载: {doi}")

        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code != 200:
                stats["failed"] += 1
                print(f"   ❌ HTTP {response.status_code}")
                continue

            # 检查内容类型 / Check content type
            content_type = response.headers.get("Content-Type", "").lower()
            
            # 如果是 PDF，直接保存 / If it's PDF, save directly
            if "application/pdf" in content_type or response.content[:4] == b"%PDF":
                with open(output_path, "wb") as f:
                    f.write(response.content)
                stats["success"] += 1
                print(f"   ✅ 成功: {output_path.name}")
            # 如果是 HTML，尝试提取 PDF 链接 / If HTML, try to extract PDF link
            elif "text/html" in content_type:
                html = response.text
                
                # 检查是否是错误页面 / Check if it's an error page
                if "not available" in html.lower() or "article is not available" in html.lower():
                    stats["failed"] += 1
                    print(f"   ❌ 文章不可用 / Article not available")
                    continue
                
                # 尝试从 HTML 中提取 PDF URL / Try to extract PDF URL from HTML
                pdf_url = None
                
                # 方法1: 查找 iframe src / Method 1: Find iframe src
                iframe_patterns = [
                    r'<iframe[^>]+src=["\']([^"\']+)["\']',
                    r'iframe\.src\s*=\s*["\']([^"\']+)["\']',
                ]
                for pattern in iframe_patterns:
                    iframe_match = re.search(pattern, html, re.IGNORECASE)
                    if iframe_match:
                        pdf_url = iframe_match.group(1)
                        # 如果是相对路径，转换为绝对路径 / Convert relative to absolute URL
                        if not pdf_url.startswith("http"):
                            pdf_url = urljoin(response.url, pdf_url)
                        break
                
                # 方法2: 查找 embed src / Method 2: Find embed src
                if not pdf_url:
                    embed_match = re.search(r'<embed[^>]+src=["\']([^"\']+\.pdf[^"\']*)["\']', html, re.IGNORECASE)
                    if embed_match:
                        pdf_url = embed_match.group(1)
                        if not pdf_url.startswith("http"):
                            pdf_url = urljoin(response.url, pdf_url)
                
                # 方法3: 查找 button 或 link 中的 PDF URL / Method 3: Find PDF URL in button or link
                if not pdf_url:
                    button_match = re.search(r'<button[^>]+onclick=["\'][^"\']*["\']([^"\']+\.pdf[^"\']*)["\']', html, re.IGNORECASE)
                    if button_match:
                        pdf_url = button_match.group(1)
                        if not pdf_url.startswith("http"):
                            pdf_url = urljoin(response.url, pdf_url)
                
                # 方法4: 查找直接的 PDF 链接（更宽松的模式）/ Method 4: Find direct PDF link (more flexible pattern)
                if not pdf_url:
                    # 查找所有可能的 PDF URL / Find all possible PDF URLs
                    pdf_patterns = [
                        r'https?://[^"\'\s<>]+\.pdf[^"\'\s<>]*',
                        r'//[^"\'\s<>]+\.pdf[^"\'\s<>]*',
                        r'/downloads/[^"\'\s<>]+\.pdf',
                    ]
                    for pattern in pdf_patterns:
                        pdf_match = re.search(pattern, html, re.IGNORECASE)
                        if pdf_match:
                            pdf_url = pdf_match.group(0)
                            if pdf_url.startswith("//"):
                                pdf_url = "https:" + pdf_url
                            elif not pdf_url.startswith("http"):
                                pdf_url = urljoin(response.url, pdf_url)
                            break
                
                # 方法5: 查找 Sci-Hub 的下载链接 / Method 5: Find Sci-Hub download link
                if not pdf_url:
                    # Sci-Hub 可能使用特定的下载路径 / Sci-Hub may use specific download paths
                    download_match = re.search(r'href=["\']([^"\']*download[^"\']*\.pdf[^"\']*)["\']', html, re.IGNORECASE)
                    if download_match:
                        pdf_url = download_match.group(1)
                        if not pdf_url.startswith("http"):
                            pdf_url = urljoin(response.url, pdf_url)
                
                if pdf_url:
                    # 下载真正的 PDF / Download actual PDF
                    pdf_response = requests.get(pdf_url, headers=headers, timeout=30, stream=True)
                    if pdf_response.status_code == 200 and (pdf_response.content[:4] == b"%PDF" or "application/pdf" in pdf_response.headers.get("Content-Type", "").lower()):
                        with open(output_path, "wb") as f:
                            for chunk in pdf_response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        stats["success"] += 1
                        print(f"   ✅ 成功: {output_path.name}")
                    else:
                        stats["failed"] += 1
                        print(f"   ❌ PDF 下载失败 / PDF download failed")
                else:
                    stats["failed"] += 1
                    print(f"   ❌ 无法找到 PDF 链接 / Cannot find PDF link")
            else:
                stats["failed"] += 1
                print(f"   ❌ 未知内容类型: {content_type}")
                
        except Exception as e:
            stats["failed"] += 1
            print(f"   ❌ 失败: {e}")
            if output_path.exists():
                output_path.unlink()

        # 请求间隔 / Request delay
        if i < len(urls):
            time.sleep(1.0)

    # 打印统计 / Print statistics
    print("\n" + "=" * 60)
    print("📊 下载汇总:")
    print(f"📁 总计: {stats['total']}")
    print(f"✅ 成功: {stats['success']}")
    print(f"⏭️  跳过: {stats['skipped']}")
    print(f"❌ 失败: {stats['failed']}")
    print("=" * 60)
