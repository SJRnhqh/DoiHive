// core/check.go

package core

import (
	"fmt"
	"io/ioutil"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
)

// FileStats 文件统计信息
type FileStats struct {
	FileName       string
	TotalRecords   int
	ValidDOIs      int
	MissingCount   int
	MissingDetails []MissingRecord
}

// MissingRecord 缺失 DOI 的记录
type MissingRecord struct {
	Index   int
	Content string
}

// CheckResult 检查结果
type CheckResult struct {
	TotalFiles    int
	TotalRecords  int
	TotalDOIs     int
	UniqueDOIs    int
	MissingDOIs   int
	Coverage      float64
	FileStats     []FileStats
	AllDOIs       []string
	DuplicateDOIs map[string]map[string]int // DOI -> filename -> count
}

// CheckDOIs 检查 archive 目录下的所有文件中的 DOI 记录
func CheckDOIs(archiveDir string) (*CheckResult, error) {
	// 检查目录是否存在
	if _, err := os.Stat(archiveDir); os.IsNotExist(err) {
		return nil, fmt.Errorf("目录不存在: %s", archiveDir)
	}

	// 获取所有 .txt 文件
	txtFiles, err := getTxtFiles(archiveDir)
	if err != nil {
		return nil, err
	}

	if len(txtFiles) == 0 {
		return nil, fmt.Errorf("%s 下没有 .txt 文件", archiveDir)
	}

	result := &CheckResult{
		FileStats:     make([]FileStats, 0),
		AllDOIs:       make([]string, 0),
		DuplicateDOIs: make(map[string]map[string]int),
	}

	// 处理每个文件
	for _, filePath := range txtFiles {
		stats, err := analyzeFile(filePath)
		if err != nil {
			continue
		}

		result.FileStats = append(result.FileStats, *stats)
		result.TotalRecords += stats.TotalRecords
		result.TotalDOIs += stats.ValidDOIs
		result.MissingDOIs += stats.MissingCount

		// 收集所有 DOI
		dois := extractDOIsFromFile(filePath)
		for _, doi := range dois {
			result.AllDOIs = append(result.AllDOIs, doi)
			// 记录 DOI 出现的文件
			if result.DuplicateDOIs[doi] == nil {
				result.DuplicateDOIs[doi] = make(map[string]int)
			}
			fileName := filepath.Base(filePath)
			result.DuplicateDOIs[doi][fileName]++
		}
	}

	// 计算唯一 DOI 数
	uniqueDOIs := make(map[string]bool)
	for _, doi := range result.AllDOIs {
		uniqueDOIs[doi] = true
	}
	result.UniqueDOIs = len(uniqueDOIs)
	result.TotalFiles = len(txtFiles)

	// 计算覆盖率
	if result.TotalRecords > 0 {
		result.Coverage = float64(result.TotalDOIs) / float64(result.TotalRecords) * 100
	}

	return result, nil
}

// ExtractDOIs 从 archive 目录提取所有有效的 DOI
func ExtractDOIs(archiveDir string) ([]string, error) {
	if _, err := os.Stat(archiveDir); os.IsNotExist(err) {
		return nil, fmt.Errorf("目录不存在: %s", archiveDir)
	}

	txtFiles, err := getTxtFiles(archiveDir)
	if err != nil {
		return nil, err
	}

	allDOIs := make([]string, 0)
	for _, filePath := range txtFiles {
		dois := extractDOIsFromFile(filePath)
		allDOIs = append(allDOIs, dois...)
	}

	// 去重
	uniqueDOIs := make(map[string]bool)
	for _, doi := range allDOIs {
		uniqueDOIs[doi] = true
	}

	result := make([]string, 0, len(uniqueDOIs))
	for doi := range uniqueDOIs {
		result = append(result, doi)
	}

	return result, nil
}

// 辅助函数

func getTxtFiles(dir string) ([]string, error) {
	files, err := ioutil.ReadDir(dir)
	if err != nil {
		return nil, err
	}

	txtFiles := make([]string, 0)
	for _, file := range files {
		if !file.IsDir() && strings.HasSuffix(file.Name(), ".txt") {
			txtFiles = append(txtFiles, filepath.Join(dir, file.Name()))
		}
	}

	sort.Strings(txtFiles)
	return txtFiles, nil
}

func analyzeFile(filePath string) (*FileStats, error) {
	content, err := readFileText(filePath)
	if err != nil {
		return nil, err
	}

	records := parseWosRecords(content)
	stats := &FileStats{
		FileName:       filepath.Base(filePath),
		TotalRecords:   len(records),
		MissingDetails: make([]MissingRecord, 0),
	}

	doiRegex := regexp.MustCompile(`^10\.\d{4,9}/[^\s]+$`)

	for idx, lines := range records {
		doi := extractDOIFromRecord(lines)
		if doi != "" && doiRegex.MatchString(doi) {
			stats.ValidDOIs++
		} else {
			stats.MissingCount++
			stats.MissingDetails = append(stats.MissingDetails, MissingRecord{
				Index:   idx,
				Content: strings.Join(lines, "\n"),
			})
		}
	}

	return stats, nil
}

func parseWosRecords(text string) [][]string {
	blocks := strings.Split(text, "\nER\n")
	records := make([][]string, 0)

	for _, block := range blocks {
		block = strings.TrimSpace(block)
		if block == "" || block == "EF" || (strings.HasPrefix(block, "EF") && len(strings.Fields(block)) == 1) {
			continue
		}

		lines := strings.Split(block, "\n")
		lines = append(lines, "ER")
		records = append(records, lines)
	}

	return records
}

func extractDOIFromRecord(lines []string) string {
	for _, line := range lines {
		if strings.HasPrefix(line, "DI") {
			parts := strings.Fields(line)
			if len(parts) >= 2 {
				return strings.Join(parts[1:], " ")
			}
		}
	}
	return ""
}

func extractDOIsFromFile(filePath string) []string {
	content, err := readFileText(filePath)
	if err != nil {
		return nil
	}

	records := parseWosRecords(content)
	dois := make([]string, 0)
	doiRegex := regexp.MustCompile(`^10\.\d{4,9}/[^\s]+$`)

	for _, lines := range records {
		doi := extractDOIFromRecord(lines)
		if doi != "" && doiRegex.MatchString(doi) {
			dois = append(dois, doi)
		}
	}

	return dois
}

func readFileText(filePath string) (string, error) {
	// 尝试 UTF-8-SIG
	data, err := ioutil.ReadFile(filePath)
	if err != nil {
		return "", err
	}

	// 移除 BOM
	if len(data) >= 3 && data[0] == 0xEF && data[1] == 0xBB && data[2] == 0xBF {
		data = data[3:]
	}

	content := string(data)

	// 如果包含无效字符，尝试 latin1
	if !isValidUTF8(content) {
		data, _ = ioutil.ReadFile(filePath)
		content = string(data)
	}

	return content, nil
}

func isValidUTF8(s string) bool {
	for _, r := range s {
		if r == 0xFFFD {
			return false
		}
	}
	return true
}
