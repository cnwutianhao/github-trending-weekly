#!/usr/bin/env python3
"""抓取 GitHub Trending (weekly)，生成 Markdown 周报。
   纯标准库实现，零外部依赖。
   支持两种模式：
     python3 fetch_trending.py             # 自动抓取
     python3 fetch_trending.py FILE.html   # 从本地 HTML 文件解析
"""

import html
import os
import re
import sys
import urllib.request
from datetime import date, timedelta


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


def parse_repos(html_str: str) -> list[dict]:
    """解析 GitHub Trending 页面，返回仓库列表。"""
    repos = []

    # 每个仓库由 <article class="Box-row"> 包裹
    blocks = re.split(r'<article\s+class="Box-row"', html_str)[1:]

    if not blocks:
        # GitHub 可能改了 HTML class，用泛型 <article> 兜底
        blocks = re.split(r'<article\b[^>]*>', html_str)[1:]
        blocks = [b for b in blocks if '/stargazers' in b]

    for block in blocks:
        article_end = block.find("</article>")
        if article_end != -1:
            block = block[:article_end]

        repo = {}

        # --- 仓库名: h2 > a ---
        h2_m = re.search(r'<h2[^>]*>\s*<a\s+href="/([^"]+)"', block)
        if not h2_m:
            continue
        full_name = h2_m.group(1)
        repo["full_name"] = full_name
        parts = full_name.split("/")
        repo["owner"] = parts[0]
        repo["name"] = parts[1]

        # --- 描述: <p class="col-9 ..."> ---
        desc_m = re.search(r'<p\s+class="col-9\s+color-fg-muted[^"]*"\s*>(.*?)</p>', block, re.DOTALL)
        if desc_m:
            desc = re.sub(r'<[^>]+>', '', desc_m.group(1)).strip()
            desc = html.unescape(desc).replace("\n", " ").replace("  ", " ")
            repo["description"] = desc.strip()
        else:
            repo["description"] = ""

        # --- 语言 ---
        lang_m = re.search(r'<span\s+itemprop="programmingLanguage">\s*([^<]+)\s*</span>', block)
        repo["language"] = lang_m.group(1).strip() if lang_m else ""

        # --- 总 star 数 ---
        star_m = re.search(r'href="/[^"]+/stargazers"[^>]*>\s*([\d,]+)\s*</a>', block)
        repo["total_stars"] = star_m.group(1).replace(",", "") if star_m else "0"

        # --- 本周 star 数 ---
        week_m = re.search(
            r'<span\s+class="d-inline-block\s+float-sm-right"[^>]*>\s*([\d,]+)\s+stars?\s+this\s+week',
            block,
            re.IGNORECASE,
        )
        repo["stars_week"] = week_m.group(1).replace(",", "") if week_m else "0"

        # --- forks 数 ---
        fork_m = re.search(r'href="/[^"]+/forks"[^>]*>\s*([\d,]+)\s*</a>', block)
        repo["forks"] = fork_m.group(1).replace(",", "") if fork_m else "0"

        # --- built by ---
        built_by = re.findall(r'href="/([^"]+)"[^>]*>\s*<img[^>]*rounded-2[^>]*>', block)
        repo["built_by"] = [u for u in built_by if "/" not in u or u.startswith("apps/")]

        repos.append(repo)

    return repos


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

    return "\n".join(lines)


def main():
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        print(f"Reading HTML from {filepath}...")
        with open(filepath, "r", encoding="utf-8") as f:
            html_str = f.read()
    else:
        print("Fetching GitHub Trending (weekly)...")
        html_str = fetch_html(TRENDING_URL)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Parsing repositories...")
    repos = parse_repos(html_str)
    print(f"Found {len(repos)} repositories")

    if len(repos) == 0:
        print("--- HTML preview (first 3000 chars) ---")
        print(html_str[:3000])
        print("--- end preview ---")

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
