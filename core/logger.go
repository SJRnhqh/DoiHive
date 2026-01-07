// core/logger.go

package core

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// Logger 日志记录器
type Logger struct {
	LogDir    string
	Timestamp string
}

// NewLogger 创建新的日志记录器
func NewLogger(baseDir string) (*Logger, error) {
	logDir := filepath.Join(baseDir, "logs")
	if err := os.MkdirAll(logDir, 0755); err != nil {
		return nil, fmt.Errorf("无法创建日志目录: %v", err)
	}

	timestamp := time.Now().Format("2006-01-02_15-04-05")
	return &Logger{
		LogDir:    logDir,
		Timestamp: timestamp,
	}, nil
}

// SaveFailedDOIs 保存失败的 DOI 列表
func (l *Logger) SaveFailedDOIs(errors []DownloadError) error {
	if len(errors) == 0 {
		return nil
	}

	filename := filepath.Join(l.LogDir, fmt.Sprintf("failed_dois_%s.txt", l.Timestamp))
	file, err := os.Create(filename)
	if err != nil {
		return fmt.Errorf("无法创建失败 DOI 文件: %v", err)
	}
	defer file.Close()

	// 写入头部信息
	fmt.Fprintf(file, "# 失败的 DOI 列表\n")
	fmt.Fprintf(file, "# 生成时间: %s\n", time.Now().Format("2006-01-02 15:04:05"))
	fmt.Fprintf(file, "# 总计: %d 个\n", len(errors))
	fmt.Fprintf(file, "#\n")
	fmt.Fprintf(file, "# 格式: DOI | 错误原因\n")
	fmt.Fprintf(file, "#\n\n")

	// 按错误类型分组统计
	errorStats := make(map[string]int)
	for _, e := range errors {
		// 简化错误信息用于统计
		errType := simplifyError(e.Error)
		errorStats[errType]++
	}

	// 写入错误统计
	fmt.Fprintf(file, "# === 错误统计 ===\n")
	for errType, count := range errorStats {
		fmt.Fprintf(file, "# %s: %d 个\n", errType, count)
	}
	fmt.Fprintf(file, "#\n\n")

	// 写入详细列表
	fmt.Fprintf(file, "# === 详细列表 ===\n\n")
	for _, e := range errors {
		fmt.Fprintf(file, "%s | %s\n", e.DOI, e.Error)
	}

	return nil
}

// SaveDOIsOnly 仅保存失败的 DOI（不含错误信息，方便重试）
func (l *Logger) SaveDOIsOnly(errors []DownloadError) error {
	if len(errors) == 0 {
		return nil
	}

	filename := filepath.Join(l.LogDir, fmt.Sprintf("retry_dois_%s.txt", l.Timestamp))
	file, err := os.Create(filename)
	if err != nil {
		return fmt.Errorf("无法创建重试 DOI 文件: %v", err)
	}
	defer file.Close()

	// 写入头部信息
	fmt.Fprintf(file, "# 需要重试的 DOI 列表\n")
	fmt.Fprintf(file, "# 生成时间: %s\n", time.Now().Format("2006-01-02 15:04:05"))
	fmt.Fprintf(file, "# 总计: %d 个\n", len(errors))
	fmt.Fprintf(file, "#\n\n")

	// 只写入 DOI
	for _, e := range errors {
		fmt.Fprintf(file, "%s\n", e.DOI)
	}

	return nil
}

// SaveDownloadLog 保存完整的下载日志
func (l *Logger) SaveDownloadLog(stats *DownloadStats) error {
	filename := filepath.Join(l.LogDir, fmt.Sprintf("download_log_%s.txt", l.Timestamp))
	file, err := os.Create(filename)
	if err != nil {
		return fmt.Errorf("无法创建日志文件: %v", err)
	}
	defer file.Close()

	// 写入头部信息
	fmt.Fprintf(file, "========================================\n")
	fmt.Fprintf(file, "      DoiHive 下载日志\n")
	fmt.Fprintf(file, "========================================\n\n")
	fmt.Fprintf(file, "生成时间: %s\n\n", time.Now().Format("2006-01-02 15:04:05"))

	// 写入统计信息
	fmt.Fprintf(file, "=== 下载统计 ===\n\n")
	fmt.Fprintf(file, "总计: %d 个文件\n", stats.Total)
	fmt.Fprintf(file, "成功: %d 个文件\n", stats.Success)
	fmt.Fprintf(file, "跳过: %d 个文件\n", stats.Skip)
	fmt.Fprintf(file, "失败: %d 个文件\n", stats.Failed)

	if stats.Total > 0 {
		successRate := float64(stats.Success) / float64(stats.Total) * 100
		fmt.Fprintf(file, "成功率: %.2f%%\n", successRate)
	}

	if stats.TotalSize > 0 {
		fmt.Fprintf(file, "总大小: %s\n", formatFileSize(stats.TotalSize))
	}

	fmt.Fprintf(file, "总耗时: %s\n", formatDurationLog(stats.TotalTime))

	// 计算平均耗时
	if len(stats.AllTimes) > 0 {
		var totalAllTime time.Duration
		for _, t := range stats.AllTimes {
			totalAllTime += t
		}
		avgAllTime := totalAllTime / time.Duration(len(stats.AllTimes))
		fmt.Fprintf(file, "平均耗时: %s\n", formatDurationLog(avgAllTime))
	}

	if len(stats.SuccessTime) > 0 {
		var totalSuccessTime time.Duration
		for _, t := range stats.SuccessTime {
			totalSuccessTime += t
		}
		avgSuccessTime := totalSuccessTime / time.Duration(len(stats.SuccessTime))
		fmt.Fprintf(file, "成功平均耗时: %s\n", formatDurationLog(avgSuccessTime))
	}

	// 写入错误详情
	if len(stats.Errors) > 0 {
		fmt.Fprintf(file, "\n=== 错误详情 (%d 个) ===\n\n", len(stats.Errors))

		// 按错误类型分组
		errorGroups := make(map[string][]DownloadError)
		for _, e := range stats.Errors {
			errType := simplifyError(e.Error)
			errorGroups[errType] = append(errorGroups[errType], e)
		}

		// 写入分组错误
		for errType, errs := range errorGroups {
			fmt.Fprintf(file, "--- %s (%d 个) ---\n", errType, len(errs))
			for _, e := range errs {
				fmt.Fprintf(file, "  - %s\n", e.DOI)
			}
			fmt.Fprintf(file, "\n")
		}
	}

	fmt.Fprintf(file, "\n========================================\n")
	fmt.Fprintf(file, "日志结束\n")
	fmt.Fprintf(file, "========================================\n")

	return nil
}

// GetLogFilePaths 获取日志文件路径
func (l *Logger) GetLogFilePaths() (logFile, failedFile, retryFile string) {
	logFile = filepath.Join(l.LogDir, fmt.Sprintf("download_log_%s.txt", l.Timestamp))
	failedFile = filepath.Join(l.LogDir, fmt.Sprintf("failed_dois_%s.txt", l.Timestamp))
	retryFile = filepath.Join(l.LogDir, fmt.Sprintf("retry_dois_%s.txt", l.Timestamp))
	return
}

// simplifyError 简化错误信息用于分类
func simplifyError(errMsg string) string {
	lowerErr := strings.ToLower(errMsg)

	if strings.Contains(lowerErr, "不可用") || strings.Contains(lowerErr, "not available") {
		return "文章不可用"
	}
	if strings.Contains(lowerErr, "验证码") || strings.Contains(lowerErr, "captcha") {
		return "验证码拦截"
	}
	if strings.Contains(lowerErr, "403") {
		return "HTTP 403 错误"
	}
	if strings.Contains(lowerErr, "404") || strings.Contains(lowerErr, "未找到") {
		return "页面不存在"
	}
	if strings.Contains(lowerErr, "超时") || strings.Contains(lowerErr, "timeout") {
		return "请求超时"
	}
	if strings.Contains(lowerErr, "无法提取") {
		return "无法提取 PDF URL"
	}
	if strings.Contains(lowerErr, "pdf") && strings.Contains(lowerErr, "有效") {
		return "无效的 PDF 文件"
	}

	return "其他错误"
}

// formatFileSize 格式化文件大小
func formatFileSize(size int64) string {
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

// formatDurationLog 格式化时间（用于日志）
func formatDurationLog(d time.Duration) string {
	if d < time.Second {
		return fmt.Sprintf("%.2fms", float64(d)/float64(time.Millisecond))
	} else if d < time.Minute {
		return fmt.Sprintf("%.2fs", d.Seconds())
	} else if d < time.Hour {
		return fmt.Sprintf("%.2f分钟", d.Minutes())
	}
	return fmt.Sprintf("%.2f小时", d.Hours())
}
