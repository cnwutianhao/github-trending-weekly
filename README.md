# GitHub Trending Weekly 📊

每周自动抓取 GitHub 热门趋势仓库，生成中文 Markdown 周报。

## 最新周报

<!-- LATEST_REPORT_START -->
- [2026年08月10日—2026年08月16日](weekly/20260810-20260816.md)
<!-- LATEST_REPORT_END -->

所有历史报告请查看 [`weekly/`](weekly/) 目录；每份周报对应的解释/归纳/趋势分析请查看 [`analysis/`](analysis/) 目录（与周报同名，由 AI 解读生成）。

## 使用方式

### 手动运行

```bash
# 在线抓取
python3 fetch_trending.py

# 从本地 HTML 文件解析（调试用，任意本地 HTML 文件）
python3 fetch_trending.py your_trending.html
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
├── weekly/
│   └── YYYYMMDD-YYYYMMDD.md      # 周报（自动生成），每期一份
├── analysis/
│   └── YYYYMMDD-YYYYMMDD.md      # 周报解读与趋势分析（与 weekly 同名，AI 生成）
└── LICENSE                       # MIT 许可证
```

## 测试

```bash
python3 -m unittest -v
```

## 报告内容

每份周报包含：
- 标题与统计周期（周一 — 周日日期）
- 收录仓库数量与数据来源说明
- 📊 排行榜表格（排名、语言、总 Star、本周 Star、简介）
- 🔗 项目链接速查列表
- 自动生成时间页脚

## 分析文档内容

每份周报对应的 [`analysis/`](analysis/) 解读文档（与周报同名）包含：
- 本周概览与趋势总结（按主题分类归纳）
- 重点项目的解读
- 与上周榜单的对比（连续在榜 / 新进榜 / 掉榜）
- 值得长期关注的项目方向

> 由 AI 基于同名周报数据生成，非脚本自动产出。
