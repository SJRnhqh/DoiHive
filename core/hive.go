// core/hive.go

package core

import (
	"compress/gzip"
	"fmt"
	"io"
	"math/rand"
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

// setBrowserHeaders 设置完整的浏览器请求头，避免被识别为爬虫
func setBrowserHeaders(req *http.Request) {
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
	req.Header.Set("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8")
	req.Header.Set("Accept-Language", "en-US,en;q=0.9")
	req.Header.Set("Accept-Encoding", "gzip, deflate, br")
	req.Header.Set("Connection", "keep-alive")
	req.Header.Set("Upgrade-Insecure-Requests", "1")
	req.Header.Set("Sec-Fetch-Dest", "document")
	req.Header.Set("Sec-Fetch-Mode", "navigate")
	req.Header.Set("Sec-Fetch-Site", "none")
	req.Header.Set("Cache-Control", "max-age=0")
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

	var err error

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
	var info os.FileInfo
	info, err = os.Stat(pdfFilePath)
	if err == nil {
		return createResult("skip", pdfFilename, info.Size(), doi, "")
	}

	// 添加随机延迟，避免请求过快被识别为爬虫
	delay := time.Duration(500+rand.Intn(1500)) * time.Millisecond // 0.5-2.0 秒
	time.Sleep(delay)

	// 第一步：获取页面 HTML（带重试机制）
	const maxRetries = 3
	retryDelay := 2 * time.Second // 初始重试延迟

	var resp *http.Response
	var req *http.Request
	for attempt := 0; attempt < maxRetries; attempt++ {
		req, err = http.NewRequest("GET", pageURL, nil)
		if err != nil {
			return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("创建请求失败: %v", err))
		}
		setBrowserHeaders(req)

		resp, err = client.Do(req)
		if err != nil {
			if attempt < maxRetries-1 {
				waitTime := retryDelay*time.Duration(attempt+1) + time.Duration(rand.Intn(2000))*time.Millisecond
				time.Sleep(waitTime)
				continue
			}
			return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("页面请求失败: %v (已重试 %d 次)", err, maxRetries))
		}

		// 如果是 403 错误，等待后重试
		if resp.StatusCode == http.StatusForbidden {
			resp.Body.Close()
			if attempt < maxRetries-1 {
				waitTime := retryDelay*time.Duration(attempt+1) + time.Duration(rand.Intn(2000))*time.Millisecond
				time.Sleep(waitTime)
				continue
			}
			return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("页面请求失败: HTTP 403 (已重试 %d 次)", maxRetries))
		}

		// 对于 404 错误，如果是第一次尝试，可以重试一次（可能是临时问题）
		if resp.StatusCode == http.StatusNotFound {
			resp.Body.Close()
			if attempt < maxRetries-1 {
				waitTime := retryDelay*time.Duration(attempt+1) + time.Duration(rand.Intn(2000))*time.Millisecond
				time.Sleep(waitTime)
				continue
			}
			return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("页面请求失败: HTTP 404 (页面不存在，已重试 %d 次)", maxRetries))
		}

		if resp.StatusCode != http.StatusOK {
			resp.Body.Close()
			return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("页面请求失败: HTTP %d", resp.StatusCode))
		}

		break // 成功，退出重试循环
	}

	if resp == nil {
		return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("页面请求失败: 已重试 %d 次", maxRetries))
	}
	defer resp.Body.Close()

	// 读取 HTML 内容（处理 gzip 压缩）
	var reader io.Reader = resp.Body
	if resp.Header.Get("Content-Encoding") == "gzip" {
		gzReader, err := gzip.NewReader(resp.Body)
		if err != nil {
			return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("解压缩失败: %v", err))
		}
		defer gzReader.Close()
		reader = gzReader
	}

	htmlContent, err := io.ReadAll(reader)
	if err != nil {
		return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("读取页面内容失败: %v", err))
	}

	// 解析 HTML（使用读取的内容）
	doc, err := goquery.NewDocumentFromReader(strings.NewReader(string(htmlContent)))
	if err != nil {
		return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("HTML 解析失败: %v", err))
	}

	// 第二步：提取 PDF URL（同时使用 goquery 和原始 HTML）
	pdfURL := extractPDFURL(doc, string(htmlContent), pageURL)
	if pdfURL == "" {
		// 添加调试信息：检查页面内容
		htmlStr := string(htmlContent)
		title := doc.Find("title").Text()

		// 检查是否是错误页面，提供更友好的错误信息
		errorMsg := "未能从页面中提取 PDF URL"
		lowerHtml := strings.ToLower(htmlStr)
		lowerTitle := strings.ToLower(title)

		// 优先检查是否是文章不可用的情况
		if strings.Contains(lowerTitle, "article is not available") ||
			strings.Contains(lowerHtml, "article is not available") ||
			strings.Contains(lowerHtml, "not available through sci-hub") {
			errorMsg = "文章在 Sci-Hub 上不可用"
		} else if strings.Contains(lowerHtml, "captcha") {
			errorMsg += " (检测到验证码)"
		} else if strings.Contains(lowerHtml, "not found") || strings.Contains(lowerHtml, "404") {
			errorMsg += " (页面未找到)"
		} else if title != "" {
			// 如果页面有标题，添加到错误信息中
			if len(title) > 50 {
				title = title[:50] + "..."
			}
			errorMsg += fmt.Sprintf(" (页面标题: %s)", title)
		}

		// 保存 HTML 到文件用于调试（仅在失败时）
		debugDir := filepath.Join(pdfDir, "debug")
		os.MkdirAll(debugDir, 0755)
		debugFilename := strings.ReplaceAll(doi, "/", "_")
		debugFilename = strings.ReplaceAll(debugFilename, ":", "_")
		debugFile := filepath.Join(debugDir, fmt.Sprintf("%s.html", debugFilename))
		os.WriteFile(debugFile, htmlContent, 0644)

		return createResult("failed", pdfFilename, 0, doi, errorMsg)
	}

	// 第三步：下载 PDF 文件
	// 添加随机延迟
	delay = time.Duration(300+rand.Intn(700)) * time.Millisecond // 0.3-1.0 秒
	time.Sleep(delay)

	// PDF 下载（带重试机制）
	var pdfResp *http.Response
	for attempt := 0; attempt < maxRetries; attempt++ {
		req, err = http.NewRequest("GET", pdfURL, nil)
		if err != nil {
			return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("创建 PDF 请求失败: %v", err))
		}
		setBrowserHeaders(req)
		// 为 PDF 下载添加 Referer 头
		req.Header.Set("Referer", pageURL)

		pdfResp, err = pdfClient.Do(req)
		if err != nil {
			if attempt < maxRetries-1 {
				waitTime := retryDelay*time.Duration(attempt+1) + time.Duration(rand.Intn(2000))*time.Millisecond
				time.Sleep(waitTime)
				continue
			}
			return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("PDF 下载失败: %v (已重试 %d 次)", err, maxRetries))
		}

		// 如果是 403 错误，等待后重试
		if pdfResp.StatusCode == http.StatusForbidden {
			pdfResp.Body.Close()
			if attempt < maxRetries-1 {
				waitTime := retryDelay*time.Duration(attempt+1) + time.Duration(rand.Intn(2000))*time.Millisecond
				time.Sleep(waitTime)
				continue
			}
			return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("PDF 下载失败: HTTP 403 (已重试 %d 次)", maxRetries))
		}

		if pdfResp.StatusCode != http.StatusOK {
			pdfResp.Body.Close()
			return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("PDF 下载失败: HTTP %d", pdfResp.StatusCode))
		}

		break // 成功，退出重试循环
	}

	if pdfResp == nil {
		return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("PDF 下载失败: 已重试 %d 次", maxRetries))
	}
	defer pdfResp.Body.Close()

	// 检查 Content-Type，如果不是 PDF 则提前报错
	contentType := pdfResp.Header.Get("Content-Type")
	if contentType != "" && !strings.Contains(strings.ToLower(contentType), "pdf") && !strings.Contains(strings.ToLower(contentType), "application/octet-stream") {
		if strings.Contains(strings.ToLower(contentType), "html") || strings.Contains(strings.ToLower(contentType), "text") {
			return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("PDF 下载失败: 服务器返回 HTML 而非 PDF (Content-Type: %s)", contentType))
		}
	}

	// 创建临时文件
	tmpFile, err := os.CreateTemp(pdfDir, "*.tmp")
	if err != nil {
		return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("创建临时文件失败: %v", err))
	}
	tmpPath := tmpFile.Name()
	defer os.Remove(tmpPath)

	// 处理可能的 gzip 压缩
	var pdfReader io.Reader = pdfResp.Body
	if pdfResp.Header.Get("Content-Encoding") == "gzip" {
		gzReader, err := gzip.NewReader(pdfResp.Body)
		if err != nil {
			return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("PDF 解压缩失败: %v", err))
		}
		defer gzReader.Close()
		pdfReader = gzReader
	}

	// 写入文件
	written, err := io.Copy(tmpFile, pdfReader)
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
		// 检查是否是 HTML 错误页面
		file.Seek(0, 0)
		contentStart := make([]byte, 512)
		file.Read(contentStart)
		contentStr := strings.ToLower(string(contentStart))

		errorMsg := "下载的文件不是有效的 PDF 文件"
		if strings.Contains(contentStr, "<html") || strings.Contains(contentStr, "<!doctype") {
			// 尝试提取错误信息
			if strings.Contains(contentStr, "403") || strings.Contains(contentStr, "forbidden") {
				errorMsg += " (收到 HTML 403 错误页面)"
			} else if strings.Contains(contentStr, "404") || strings.Contains(contentStr, "not found") {
				errorMsg += " (收到 HTML 404 错误页面)"
			} else if strings.Contains(contentStr, "captcha") {
				errorMsg += " (收到验证码页面)"
			} else {
				errorMsg += " (收到 HTML 错误页面而非 PDF)"
			}
		} else if len(header) > 0 && header[0] == 0x1f && header[1] == 0x8b {
			errorMsg += " (文件是 gzip 压缩格式，可能是 HTML 页面)"
		}

		return createResult("failed", pdfFilename, 0, doi, errorMsg)
	}

	// 移动到最终位置
	if err := os.Rename(tmpPath, pdfFilePath); err != nil {
		return createResult("failed", pdfFilename, 0, doi, fmt.Sprintf("移动文件失败: %v", err))
	}

	return createResult("success", pdfFilename, written, doi, "")
}

// extractPDFURL 从 HTML 中提取 PDF URL
// 同时使用 goquery 和原始 HTML 字符串进行提取
func extractPDFURL(doc *goquery.Document, htmlContent string, baseURL string) string {
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

	// 方法4：查找 iframe 标签（某些页面使用 iframe 嵌入 PDF）
	doc.Find("iframe[src]").Each(func(i int, s *goquery.Selection) {
		if pdfURL != "" {
			return
		}
		if src, exists := s.Attr("src"); exists {
			if resolved := resolveURL(base, src); resolved != "" {
				// 只接受 PDF 相关的 URL
				if strings.Contains(strings.ToLower(resolved), ".pdf") || strings.Contains(resolved, "/download/") {
					pdfURL = resolved
				}
			}
		}
	})

	if pdfURL != "" {
		return pdfURL
	}

	// 方法5：使用正则表达式从原始 HTML 中提取（备用方案）
	// 优先提取 /download/ 链接（使用 DOTALL 模式匹配多行）
	downloadPattern := regexp.MustCompile(`(?is)<div[^>]*class\s*=\s*["']download["'][^>]*>.*?<a[^>]+href\s*=\s*["']([^"']+)["']`)
	if match := downloadPattern.FindStringSubmatch(htmlContent); len(match) > 1 {
		if resolved := resolveURL(base, match[1]); resolved != "" {
			return resolved
		}
	}

	// 提取 object 标签的 data 属性（不区分大小写）
	objectPattern := regexp.MustCompile(`(?i)<object[^>]+data\s*=\s*["']([^"']+)["']`)
	if match := objectPattern.FindStringSubmatch(htmlContent); len(match) > 1 {
		data := match[1]
		if idx := strings.Index(data, "#"); idx != -1 {
			data = data[:idx]
		}
		if resolved := resolveURL(base, data); resolved != "" {
			return resolved
		}
	}

	// 方法6：查找所有包含 /download/ 或 .pdf 的链接
	doc.Find("a[href]").Each(func(i int, s *goquery.Selection) {
		if pdfURL != "" {
			return
		}
		if href, exists := s.Attr("href"); exists {
			lowerHref := strings.ToLower(href)
			if strings.Contains(lowerHref, "/download/") || strings.Contains(lowerHref, ".pdf") {
				if resolved := resolveURL(base, href); resolved != "" {
					pdfURL = resolved
				}
			}
		}
	})

	if pdfURL != "" {
		return pdfURL
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
