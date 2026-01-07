// cmd/main.go

package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"time"

	core "doihive/core"
)

func main() {
	// 定义命令行参数（支持 -a 和 --archive）
	var (
		archiveDirShort = flag.String("a", "", "Archive directory path containing WoS TXT files (required)")
		archiveDirLong  = flag.String("archive", "", "Archive directory path containing WoS TXT files (required)")
		budgetShort     = flag.Int("b", 0, "Limit number of DOIs to download (0 = all, default: 0)")
		budgetLong      = flag.Int("budget", 0, "Limit number of DOIs to download (0 = all, default: 0)")
		workersShort    = flag.Int("w", 0, "Number of concurrent workers (default: 16)")
		workersLong     = flag.Int("workers", 0, "Number of concurrent workers (default: 16)")
		pdfDir          = flag.String("pdf", "./pdf", "PDF output directory (default: ./pdf)")
		help            = flag.Bool("help", false, "Show help message")
	)

	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, "Usage: %s -a <path> [options]\n\n", os.Args[0])
		fmt.Fprintf(os.Stderr, "DoiHive - Batch download academic PDFs from DOIs via Sci-Hub\n\n")
		fmt.Fprintf(os.Stderr, "Options:\n")
		flag.PrintDefaults()
		fmt.Fprintf(os.Stderr, "\nExamples:\n")
		fmt.Fprintf(os.Stderr, "  %s -a ./archive\n", os.Args[0])
		fmt.Fprintf(os.Stderr, "  %s -a ./archive -b 10 -w 8\n", os.Args[0])
		fmt.Fprintf(os.Stderr, "  %s --archive ./archive --budget 100 --workers 4\n", os.Args[0])
	}

	flag.Parse()

	// 显示帮助信息
	if *help {
		flag.Usage()
		os.Exit(0)
	}

	// 检查必需的参数（支持 -a 或 --archive）
	var archiveDir string
	if *archiveDirShort != "" {
		archiveDir = *archiveDirShort
	} else if *archiveDirLong != "" {
		archiveDir = *archiveDirLong
	}

	if archiveDir == "" {
		fmt.Fprintf(os.Stderr, "❌ 错误: archive 目录路径是必需的\n")
		fmt.Fprintf(os.Stderr, "使用 -a 或 --archive 指定路径，或使用 -help 查看帮助信息\n")
		os.Exit(1)
	}

	// 转换为绝对路径并验证
	absPath, err := filepath.Abs(archiveDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "❌ 错误: 无法解析路径: %v\n", err)
		os.Exit(1)
	}

	// 检查目录是否存在
	if _, err := os.Stat(absPath); os.IsNotExist(err) {
		fmt.Fprintf(os.Stderr, "❌ 错误: 目录不存在: %s\n", absPath)
		os.Exit(1)
	}

	fmt.Printf("📂 Archive 目录: %s\n\n", absPath)

	// 1. 检查 DOI 记录
	fmt.Println("🔍 开始检查 DOI 记录...")
	checkResult, err := core.CheckDOIs(absPath)
	if err != nil {
		fmt.Printf("❌ 错误: %v\n", err)
		os.Exit(1)
	}

	// 显示检查结果
	printCheckResult(checkResult)

	// 2. 提取所有有效的 DOI
	fmt.Println("\n🔍 提取所有有效的 DOI...")
	dois, err := core.ExtractDOIs(absPath)
	if err != nil {
		fmt.Printf("❌ 错误: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("✅ 发现 %d 个有效 DOI\n", len(dois))

	// 3. 构建 URL
	sciHubURL := "https://sci-hub.se"
	urls := make([]string, 0, len(dois))
	for _, doi := range dois {
		url := fmt.Sprintf("%s/%s", sciHubURL, doi)
		urls = append(urls, url)
	}

	fmt.Printf("✅ 构建了 %d 个 URL\n", len(urls))

	// 根据 budget 参数限制数量
	var budget int
	if *budgetShort > 0 {
		budget = *budgetShort
	} else if *budgetLong > 0 {
		budget = *budgetLong
	}

	if budget > 0 && budget < len(urls) {
		fmt.Printf("⚠️  限制为前 %d 个 URL\n", budget)
		urls = urls[:budget]
	}

	// 确定并发数
	var workers int
	if *workersShort > 0 {
		workers = *workersShort
	} else if *workersLong > 0 {
		workers = *workersLong
	} else {
		workers = 3 // 默认值（低并发以避免 403 错误）
	}

	// 4. 下载 PDF
	fmt.Printf("\n📥 开始批量下载，使用 %d 个并发 workers...\n", workers)

	absPdfDir, err := filepath.Abs(*pdfDir)
	if err != nil {
		fmt.Printf("❌ 错误: 无法解析 PDF 目录路径: %v\n", err)
		os.Exit(1)
	}

	stats, err := core.DownloadPDFs(urls, absPdfDir, workers)
	if err != nil {
		fmt.Printf("❌ 错误: %v\n", err)
		os.Exit(1)
	}

	// 显示下载统计
	printDownloadStats(stats)
}

func printCheckResult(result *core.CheckResult) {
	fmt.Printf("\n📊 批量分析汇总:\n")
	fmt.Printf("📁 文件总数: %d\n", result.TotalFiles)
	fmt.Printf("📚 总文献记录数: %d\n", result.TotalRecords)
	fmt.Printf("✅ 总有效 DOI 数（含重复）: %d\n", result.TotalDOIs)
	fmt.Printf("🔑 唯一 DOI 数: %d\n", result.UniqueDOIs)
	fmt.Printf("❌ 总缺失 DOI 数: %d\n", result.MissingDOIs)
	if result.TotalRecords > 0 {
		fmt.Printf("📈 DOI 覆盖率: %.2f%%\n", result.Coverage)
	}

	// 显示每个文件的信息
	fmt.Println("\n文件详情:")
	for _, stats := range result.FileStats {
		fmt.Printf("📄 %s: %d 条记录", stats.FileName, stats.TotalRecords)
		if stats.MissingCount > 0 {
			fmt.Printf(" (❌ %d 条缺失 DOI)", stats.MissingCount)
		} else {
			fmt.Printf(" (✅ 全部有 DOI)")
		}
		fmt.Println()
	}
}

func printDownloadStats(stats *core.DownloadStats) {
	fmt.Printf("\n📊 下载汇总统计:\n")
	fmt.Printf("📁 总计: %d 个文件\n", stats.Total)
	fmt.Printf("✅ 成功: %d 个文件\n", stats.Success)
	fmt.Printf("⏭️  跳过: %d 个文件\n", stats.Skip)
	fmt.Printf("❌ 失败: %d 个文件\n", stats.Failed)

	if stats.Total > 0 {
		successRate := float64(stats.Success) / float64(stats.Total) * 100
		fmt.Printf("📈 成功率: %.2f%%\n", successRate)
	}

	if stats.TotalSize > 0 {
		fmt.Printf("💾 总大小: %s\n", formatSize(stats.TotalSize))
	}

	fmt.Printf("⏱️  总耗时: %s\n", formatDuration(stats.TotalTime))

	// 计算平均墙钟时间（总耗时 / 总任务数）
	if stats.Total > 0 && stats.TotalTime > 0 {
		avgWallClockTime := stats.TotalTime / time.Duration(stats.Total)
		fmt.Printf("📊 平均墙钟时间: %s/任务\n", formatDuration(avgWallClockTime))
	}

	// 计算所有任务的平均耗时
	if len(stats.AllTimes) > 0 {
		var totalAllTime time.Duration
		for _, t := range stats.AllTimes {
			totalAllTime += t
		}
		avgAllTime := totalAllTime / time.Duration(len(stats.AllTimes))
		fmt.Printf("⚡ 平均耗时: %s\n", formatDuration(avgAllTime))
	}

	// 计算成功任务的平均耗时
	if len(stats.SuccessTime) > 0 {
		var totalSuccessTime time.Duration
		for _, t := range stats.SuccessTime {
			totalSuccessTime += t
		}
		avgSuccessTime := totalSuccessTime / time.Duration(len(stats.SuccessTime))
		fmt.Printf("🚀 成功平均耗时: %s\n", formatDuration(avgSuccessTime))
	}

	if len(stats.Errors) > 0 {
		fmt.Printf("\n❌ 错误详情 (%d 个):\n", len(stats.Errors))
		for i, err := range stats.Errors {
			if i >= 10 { // 只显示前10个错误
				fmt.Printf("  ... 还有 %d 个错误\n", len(stats.Errors)-10)
				break
			}
			fmt.Printf("  - DOI: %s, 错误: %s\n", err.DOI, err.Error)
		}
	}
}

func formatSize(size int64) string {
	const unit = 1024
	if size < unit {
		return fmt.Sprintf("%d B", size)
	}
	div, exp := int64(unit), 0
	for n := size / unit; n >= unit; n /= unit {
		div *= unit
		exp++
	}
	return fmt.Sprintf("%.2f %cB", float64(size)/float64(div), "KMGTPE"[exp])
}

func formatDuration(d time.Duration) string {
	if d < time.Second {
		ms := float64(d) / float64(time.Millisecond)
		// 如果小于10ms，保留2位小数；否则保留1位小数
		if ms < 10 {
			return fmt.Sprintf("%.2fms", ms)
		}
		return fmt.Sprintf("%.1fms", ms)
	} else if d < time.Minute {
		seconds := d.Seconds()
		return fmt.Sprintf("%.3fs", seconds)
	} else if d < time.Hour {
		minutes := d.Minutes()
		return fmt.Sprintf("%.3f分钟", minutes)
	} else {
		hours := d.Hours()
		return fmt.Sprintf("%.3f小时", hours)
	}
}
