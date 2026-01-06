// core/hive.go

package core

import (
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"time"

	"github.com/PuerkitoBio/goquery"
)

// DownloadResult 下载结果
type DownloadResult struct {
	Status   string // success, skip, failed
	Filename string
	Size     int64
	DOI      string
	Error    string
	Duration time.Duration
}

// DownloadStats 下载统计
type DownloadStats struct {
	Total       int
	Success     int
	Skip        int
	Failed      int
	TotalSize   int64
	Errors      []DownloadError
	TotalTime   time.Duration   // 总耗时（墙钟时间）
	AllTimes    []time.Duration // 所有任务的时间（包括成功、失败、跳过）
	SuccessTime []time.Duration // 成功任务的时间
}

// DownloadError 下载错误信息
type DownloadError struct {
	URL   string
	DOI   string
	Error string
	Time  time.Time
}

// DownloadPDFs 批量下载 PDF 文件
func DownloadPDFs(urls []string, pdfDir string, maxWorkers int) (*DownloadStats, error) {
	// 确保输出目录存在
	if err := os.MkdirAll(pdfDir, 0755); err != nil {
		return nil, fmt.Errorf("无法创建 PDF 目录: %v", err)
	}

	stats := &DownloadStats{
		Total:       len(urls),
		Errors:      make([]DownloadError, 0),
		AllTimes:    make([]time.Duration, 0),
		SuccessTime: make([]time.Duration, 0),
	}

	// 创建复用的 HTTP 客户端（带连接池优化）
	transport := &http.Transport{
		MaxIdleConns:        maxWorkers * 2, // 最大空闲连接数
		MaxIdleConnsPerHost: maxWorkers,     // 每个主机的最大空闲连接数
		MaxConnsPerHost:     maxWorkers * 2, // 每个主机的最大连接数（包括正在使用的）
		IdleConnTimeout:     90 * time.Second,
		DisableKeepAlives:   false, // 启用连接复用
		// 启用 HTTP/2（如果服务器支持，可以提升性能）
		ForceAttemptHTTP2: true,
	}

	sharedClient := &http.Client{
		Transport: transport,
		Timeout:   10 * time.Second, // 页面请求超时
	}

	pdfClient := &http.Client{
		Transport: transport,
		Timeout:   30 * time.Second, // PDF 下载超时
	}

	// 创建 worker pool
	type jobWithTime struct {
		url       string
		startTime time.Time
	}
	jobs := make(chan jobWithTime, len(urls))
	results := make(chan DownloadResult, len(urls))

	// 启动 workers
	var wg sync.WaitGroup
	for i := 0; i < maxWorkers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for job := range jobs {
				result := downloadSinglePDF(job.url, pdfDir, sharedClient, pdfClient)
				// 计算从提交到完成的总时间（包括等待时间）
				result.Duration = time.Since(job.startTime)
				results <- result
			}
		}()
	}

	// 开始计时（在发送任务之前）
	startTime := time.Now()

	// 发送任务（记录每个任务的提交时间）
	go func() {
		for _, u := range urls {
			jobs <- jobWithTime{
				url:       u,
				startTime: time.Now(),
			}
		}
		close(jobs)
	}()

	// 等待所有 workers 完成
	go func() {
		wg.Wait()
		close(results)
	}()

	// 收集结果
	for result := range results {
		// 记录所有任务的时间（包括成功、失败、跳过）
		stats.AllTimes = append(stats.AllTimes, result.Duration)

		switch result.Status {
		case "success":
			stats.Success++
			stats.TotalSize += result.Size
			stats.SuccessTime = append(stats.SuccessTime, result.Duration)
		case "skip":
			stats.Skip++
		case "failed":
			stats.Failed++
			stats.Errors = append(stats.Errors, DownloadError{
				URL:   fmt.Sprintf("https://sci-hub.se/%s", result.DOI),
				DOI:   result.DOI,
				Error: result.Error,
				Time:  time.Now(),
			})
		}
	}
	stats.TotalTime = time.Since(startTime)

	return stats, nil
}

// downloadSinglePDF 下载单个 PDF 文件
// 注意：Duration 字段由调用者计算（从任务提交到完成的时间）
func downloadSinglePDF(pageURL string, pdfDir string, client *http.Client, pdfClient *http.Client) DownloadResult {
	// 辅助函数：创建结果（Duration 由外部计算）
	createResult := func(status, filename string, size int64, doi, errMsg string) DownloadResult {
		return DownloadResult{
			Status:   status,
			Filename: filename,
			Size:     size,
			DOI:      doi,
			Error:    errMsg,
			Duration: 0, // 由外部计算
		}
	}

	// 从 URL 中提取 DOI
	parsedURL, err := url.Parse(pageURL)
	if err != nil {
		return createResult("failed", "", 0, "", fmt.Sprintf("URL 解析失败: %v", err))
	}

	doi := strings.TrimPrefix(parsedURL.Path, "/")

	// 清理 DOI 中的特殊字符，用于文件名
	safeFilename := strings.ReplaceAll(doi, "/", "_")
	safeFilename = strings.ReplaceAll(safeFilename, ":", "_")
	pdfFilename := safeFilename + ".pdf"

	pdfFilePath := filepath.Join(pdfDir, pdfFilename)

	// 检查文件是否已存在
	if info, err := os.Stat(pdfFilePath); err == nil {
		return createResult("skip", pdfFilename, info.Size(), doi, "")
	}

	// 第一步：获取页面 HTML
	req, err := http.NewRequest("GET", pageURL, nil)
	if err != nil {
		return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("创建请求失败: %v", err))
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

	resp, err := client.Do(req)
	if err != nil {
		return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("页面请求失败: %v", err))
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("页面请求失败: HTTP %d", resp.StatusCode))
	}

	// 解析 HTML
	doc, err := goquery.NewDocumentFromReader(resp.Body)
	if err != nil {
		return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("HTML 解析失败: %v", err))
	}

	// 第二步：提取 PDF URL
	pdfURL := extractPDFURL(doc, pageURL)
	if pdfURL == "" {
		return createResult("failed", pdfFilename, 0, doi, "未能从页面中提取 PDF URL")
	}

	// 第三步：下载 PDF 文件
	req, err = http.NewRequest("GET", pdfURL, nil)
	if err != nil {
		return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("创建 PDF 请求失败: %v", err))
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

	pdfResp, err := pdfClient.Do(req)
	if err != nil {
		return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("PDF 下载失败: %v", err))
	}
	defer pdfResp.Body.Close()

	if pdfResp.StatusCode != http.StatusOK {
		return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("PDF 下载失败: HTTP %d", pdfResp.StatusCode))
	}

	// 创建临时文件
	tmpFile, err := os.CreateTemp(pdfDir, "*.tmp")
	if err != nil {
		return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("创建临时文件失败: %v", err))
	}
	tmpPath := tmpFile.Name()
	defer os.Remove(tmpPath)

	// 写入文件
	written, err := io.Copy(tmpFile, pdfResp.Body)
	tmpFile.Close()
	if err != nil {
		return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("写入文件失败: %v", err))
	}

	// 检查文件大小
	if written == 0 {
		return createResult("failed", pdfFilename, 0, doi, "下载的文件大小为 0")
	}

	// 验证文件是否为有效的 PDF（检查文件头）
	file, err := os.Open(tmpPath)
	if err != nil {
		return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("打开文件失败: %v", err))
	}
	defer file.Close()

	header := make([]byte, 4)
	if _, err := file.Read(header); err != nil {
		return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("读取文件头失败: %v", err))
	}

	if string(header) != "%PDF" {
		return createResult("failed", pdfFilename, 0, doi, "下载的文件不是有效的 PDF 文件")
	}

	// 移动到最终位置
	if err := os.Rename(tmpPath, pdfFilePath); err != nil {
		return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("移动文件失败: %v", err))
	}

	return createResult("success", pdfFilename, written, doi, "")
}

// extractPDFURL 从 HTML 中提取 PDF URL
func extractPDFURL(doc *goquery.Document, baseURL string) string {
	base, err := url.Parse(baseURL)
	if err != nil {
		return ""
	}

	var pdfURL string
	var downloadURL string // 优先保存 /download/ 链接

	// 方法1：优先查找下载链接（优先查找 /download/ 路径）
	doc.Find("div.download a").Each(func(i int, s *goquery.Selection) {
		if href, exists := s.Attr("href"); exists {
			if resolved := resolveURL(base, href); resolved != "" {
				// 优先选择包含 /download/ 的链接
				if strings.Contains(resolved, "/download/") {
					downloadURL = resolved
				} else if pdfURL == "" {
					// 如果没有找到 /download/，保存第一个找到的
					pdfURL = resolved
				}
			}
		}
	})

	// 优先返回 /download/ 链接
	if downloadURL != "" {
		return downloadURL
	}
	if pdfURL != "" {
		return pdfURL
	}

	// 方法2：查找 object 标签（type='application/pdf'）
	doc.Find("object[type='application/pdf']").Each(func(i int, s *goquery.Selection) {
		if pdfURL != "" {
			return
		}
		if data, exists := s.Attr("data"); exists {
			// 移除 fragment
			if idx := strings.Index(data, "#"); idx != -1 {
				data = data[:idx]
			}
			if resolved := resolveURL(base, data); resolved != "" {
				pdfURL = resolved
			}
		}
	})

	if pdfURL != "" {
		return pdfURL
	}

	// 方法3：查找所有 object 标签（备用）
	doc.Find("object[data]").Each(func(i int, s *goquery.Selection) {
		if pdfURL != "" {
			return
		}
		if data, exists := s.Attr("data"); exists {
			// 移除 fragment
			if idx := strings.Index(data, "#"); idx != -1 {
				data = data[:idx]
			}
			if resolved := resolveURL(base, data); resolved != "" {
				pdfURL = resolved
			}
		}
	})

	if pdfURL != "" {
		return pdfURL
	}

	// 方法4：使用正则表达式从 HTML 中提取（备用方案）
	html, _ := doc.Html()

	// 优先提取 /download/ 链接
	downloadPattern := regexp.MustCompile(`<div[^>]*class\s*=\s*["']download["'][^>]*>.*?<a[^>]+href\s*=\s*["']([^"']+)["']`)
	if match := downloadPattern.FindStringSubmatch(html); len(match) > 1 {
		if resolved := resolveURL(base, match[1]); resolved != "" {
			return resolved
		}
	}

	// 提取 object 标签的 data 属性
	objectPattern := regexp.MustCompile(`<object[^>]+data\s*=\s*["']([^"']+)["']`)
	if match := objectPattern.FindStringSubmatch(html); len(match) > 1 {
		data := match[1]
		if idx := strings.Index(data, "#"); idx != -1 {
			data = data[:idx]
		}
		if resolved := resolveURL(base, data); resolved != "" {
			return resolved
		}
	}

	return ""
}

// resolveURL 解析相对 URL 为绝对 URL（类似 Python 的 urljoin）
func resolveURL(base *url.URL, ref string) string {
	if ref == "" {
		return ""
	}

	// 如果是绝对 URL，直接返回
	if strings.HasPrefix(ref, "http://") || strings.HasPrefix(ref, "https://") {
		return ref
	}

	// 解析相对路径
	refURL, err := url.Parse(ref)
	if err != nil {
		return ""
	}

	// 合并 URL（类似 Python 的 urljoin）
	resolved := base.ResolveReference(refURL)
	return resolved.String()
}
