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
import tempfile
import urllib.request
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path


TRENDING_URL = "https://github.com/trending?since=weekly"
BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "weekly"
README_PATH = BASE_DIR / "README.md"
LATEST_REPORT_START = "<!-- LATEST_REPORT_START -->"
LATEST_REPORT_END = "<!-- LATEST_REPORT_END -->"


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


def update_latest_report(readme: str, monday: date, sunday: date, report_path: str) -> str:
    """更新 README 中的最新周报链接，保留标记之外的内容。"""
    if readme.count(LATEST_REPORT_START) != 1 or readme.count(LATEST_REPORT_END) != 1:
        raise ValueError("README 必须包含唯一的 LATEST_REPORT_START 和 LATEST_REPORT_END 标记")

    start = readme.index(LATEST_REPORT_START) + len(LATEST_REPORT_START)
    end = readme.index(LATEST_REPORT_END)
    if start > end:
        raise ValueError("README 中的 LATEST_REPORT 标记顺序不正确")

    label = f"{monday.strftime('%Y年%m月%d日')}—{sunday.strftime('%Y年%m月%d日')}"
    latest = f"\n- [{label}]({report_path})\n"
    return readme[:start] + latest + readme[end:]


def atomic_write(path: Path, content: str) -> None:
    """通过同目录临时文件原子替换文本文件。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)
        os.replace(temp_path, path)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def publish_report(filepath: Path, report: str, readme_path: Path, updated_readme: str) -> None:
    """发布周报和 README；README 更新失败时回滚周报。"""
    filepath = Path(filepath)
    previous_report = filepath.read_text(encoding="utf-8") if filepath.exists() else None
    atomic_write(filepath, report)
    try:
        atomic_write(Path(readme_path), updated_readme)
    except Exception:
        if previous_report is None:
            filepath.unlink(missing_ok=True)
        else:
            atomic_write(filepath, previous_report)
        raise


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

    monday = first_day_of_this_week()
    sunday = sunday_from_monday(monday)
    report = generate_report(repos, monday, sunday)

    filename = f"{monday.strftime('%Y%m%d')}-{sunday.strftime('%Y%m%d')}.md"
    filepath = Path(OUTPUT_DIR) / filename
    with open(README_PATH, "r", encoding="utf-8") as f:
        readme = f.read()
    report_path = (Path("weekly") / filename).as_posix()
    updated_readme = update_latest_report(readme, monday, sunday, report_path)

    publish_report(filepath, report, Path(README_PATH), updated_readme)

    print(f"✅ Report saved to {filepath}")
    print(f"✅ Latest report link updated in {README_PATH}")

    sorted_repos = sorted(repos, key=lambda r: int(r["stars_week"]), reverse=True)
    print(f"\n--- Top 5 ({len(repos)} repos total) ---")
    for i, r in enumerate(sorted_repos[:5], 1):
        print(f"  {i}. {r['full_name']} (+{r['stars_week']} stars) — {r['description'][:60]}")


if __name__ == "__main__":
    main()
