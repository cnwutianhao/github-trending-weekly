#!/usr/bin/env python3
"""抓取 GitHub Trending (weekly)，生成 Markdown 周报。
   纯标准库实现，零外部依赖。
   支持两种模式：
     python3 fetch_trending.py             # 自动抓取
     python3 fetch_trending.py FILE.html   # 从本地 HTML 文件解析
"""

import os
import re
import sys
import urllib.request
from datetime import date, timedelta
from html.parser import HTMLParser


TRENDING_URL = "https://github.com/trending?since=weekly"
OUTPUT_DIR = "weekly"


def first_day_of_this_week() -> date:
    """本周一（ISO week starts with Monday）"""
    today = date.today()
    return today - timedelta(days=today.weekday())


def sunday_from_monday(monday: date) -> date:
    return monday + timedelta(days=6)


def fetch_html(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "GitHub-Trending-Bot/1.0",
            "Accept": "text/html",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


class TrendingParser(HTMLParser):
    """用容错的标准库 HTML 解析器读取 Trending 仓库卡片。"""

    VOID_ELEMENTS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.repos = []
        self.repo = None
        self.article_depth = 0
        self.capture = None
        self.capture_depth = 0
        self.text = []

    @staticmethod
    def _classes(attrs):
        return set(dict(attrs).get("class", "").split())

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "article":
            self.article_depth += 1
            if self.article_depth == 1:
                self.repo = {"description": "", "language": "", "total_stars": "0", "stars_week": "0", "forks": "0"}
            return
        if not self.repo:
            return

        if self.capture and tag not in self.VOID_ELEMENTS:
            self.capture_depth += 1

        href = attrs_dict.get("href", "")
        if tag == "a" and not self.repo.get("full_name"):
            match = re.fullmatch(r"/([^/]+/[^/]+)", href)
            if match:
                full_name = match.group(1)
                owner, name = full_name.split("/", 1)
                self.repo.update(full_name=full_name, owner=owner, name=name)

        classes = self._classes(attrs)
        if tag == "p" and "color-fg-muted" in classes:
            self._start_capture("description")
        elif tag == "span" and attrs_dict.get("itemprop") == "programmingLanguage":
            self._start_capture("language")
        elif tag == "a" and href.endswith("/stargazers"):
            self._start_capture("total_stars")
        elif tag == "a" and href.endswith("/forks"):
            self._start_capture("forks")
        elif tag == "span" and {"float-sm-right", "d-inline-block"}.issubset(classes):
            self._start_capture("stars_week")

    def _start_capture(self, field):
        self.capture = field
        self.capture_depth = 1
        self.text = []

    def handle_data(self, data):
        if self.capture:
            self.text.append(data)

    def handle_endtag(self, tag):
        if self.capture and tag in self.VOID_ELEMENTS:
            return
        if self.capture:
            self.capture_depth -= 1
            if self.capture_depth == 0:
                value = " ".join("".join(self.text).split())
                if self.capture in {"total_stars", "forks", "stars_week"}:
                    match = re.search(r"[\d,]+", value)
                    value = match.group(0).replace(",", "") if match else "0"
                self.repo[self.capture] = value
                self.capture = None
                self.text = []

        if tag == "article" and self.article_depth:
            self.article_depth -= 1
            if self.article_depth == 0:
                if self.repo.get("full_name"):
                    self.repo["built_by"] = []
                    self.repos.append(self.repo)
                self.repo = None


def parse_repos(html_str: str) -> list[dict]:
    """解析 GitHub Trending 页面，返回仓库列表。"""
    parser = TrendingParser()
    parser.feed(html_str)
    parser.close()
    return parser.repos


def format_number(n: str) -> str:
    num = int(n)
    if num >= 1000:
        return f"{num/1000:.1f}k"
    return str(num)


def generate_report(repos: list[dict], monday: date, sunday: date) -> str:
    """生成 Markdown 周报。"""
    lines = []
    lines.append(f"# GitHub 本周热门趋势")
    lines.append("")
    lines.append(f"**{monday.strftime('%Y年%m月%d日')}（周一）— {sunday.strftime('%Y年%m月%d日')}（周日）**")
    lines.append("")
    lines.append(f"> 共收录 {len(repos)} 个热门仓库。数据来源：[GitHub Trending](https://github.com/trending?since=weekly)")
    lines.append("")

    sorted_repos = sorted(repos, key=lambda r: int(r["stars_week"]), reverse=True)

    lines.append("---")
    lines.append("")
    lines.append("## 📊 排行榜")
    lines.append("")
    lines.append("| # | 项目 | 语言 | ⭐ 总计 | 🔥 本周 | 简介 |")
    lines.append("|---|------|------|---------|----------|------|")

    for i, r in enumerate(sorted_repos, 1):
        name = f"[{r['full_name']}](https://github.com/{r['full_name']})"
        lang = r["language"] or "—"
        stars = format_number(r["total_stars"])
        week = format_number(r["stars_week"])
        desc = r["description"][:100] + ("..." if len(r["description"]) > 100 else "")
        desc = desc.replace("|", "\\|")
        lines.append(f"| {i} | {name} | {lang} | {stars} | +{week} | {desc} |")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 🔗 项目链接速查")
    lines.append("")
    for i, r in enumerate(sorted_repos, 1):
        lines.append(f"{i}. [{r['full_name']}](https://github.com/{r['full_name']}) — {r['description'][:80]}")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*自动生成于 {date.today().isoformat()} | [GitHub Trending Weekly](https://github.com/trending?since=weekly)*")

    return "\n".join(lines) + "\n"


def main():
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        print(f"Reading HTML from {filepath}...")
        with open(filepath, "r", encoding="utf-8") as f:
            html_str = f.read()
    else:
        print("Fetching GitHub Trending (weekly)...")
        html_str = fetch_html(TRENDING_URL)

    print("Parsing repositories...")
    repos = parse_repos(html_str)
    print(f"Found {len(repos)} repositories")

    if len(repos) == 0:
        raise RuntimeError("未解析到任何仓库；GitHub 页面结构可能已变化，拒绝生成空周报")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    monday = first_day_of_this_week()
    sunday = sunday_from_monday(monday)
    report = generate_report(repos, monday, sunday)

    filename = f"{monday.strftime('%Y%m%d')}-{sunday.strftime('%Y%m%d')}.md"
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"✅ Report saved to {filepath}")

    sorted_repos = sorted(repos, key=lambda r: int(r["stars_week"]), reverse=True)
    print(f"\n--- Top 5 ({len(repos)} repos total) ---")
    for i, r in enumerate(sorted_repos[:5], 1):
        print(f"  {i}. {r['full_name']} (+{r['stars_week']} stars) — {r['description'][:60]}")


if __name__ == "__main__":
    main()
