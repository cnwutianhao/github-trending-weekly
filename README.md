# GitHub Trending Weekly 📊

每周自动抓取 GitHub 热门趋势仓库，生成中文 Markdown 周报。

## 最新周报

<!-- LATEST_REPORT_START -->
- [2026年07月27日—2026年08月02日](weekly/20260727-20260802.md)
<!-- LATEST_REPORT_END -->

所有历史报告请查看 [`weekly/`](weekly/) 目录。

## 使用方式

### 手动运行

```bash
# 在线抓取
python3 fetch_trending.py

# 从本地 HTML 文件解析（调试用）
python3 fetch_trending.py test_trending.html
```

### 自动运行

通过 GitHub Actions 每周一 **北京时间 00:00** 自动触发，生成的报告保存在 `weekly/` 目录下。

如需手动触发，点击仓库 Actions 页面的 `Weekly GitHub Trending` → `Run workflow`。

### 文件命名规则

报告文件名格式：`周一日期-周日日期.md`，例如 `20260727-20260802.md`。

## 目录结构

```
.
├── fetch_trending.py          # 抓取+解析脚本（纯标准库，零依赖）
├── test_fetch_trending.py     # 单元测试
├── .github/workflows/
│   └── trending.yml           # GitHub Actions 定时任务
└── weekly/
    └── 20260727-20260802.md   # 周报
```

## 测试

```bash
python3 -m unittest -v
```

## 报告内容

每份周报包含：
- 📊 排行榜表格（排名、语言、总 Star、本周 Star、简介）
- 🔗 项目链接速查列表
