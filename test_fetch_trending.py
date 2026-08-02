import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import fetch_trending


TRENDING_HTML = """
<html><body>
<article data-hpc class="Box-row">
  <h2 class="h3 lh-condensed">
    <a data-view-component="true" href="/octo-org/hello-world">octo-org / hello-world</a>
  </h2>
  <p class="color-fg-muted col-9 my-1 pr-4">A <strong>useful</strong><br/><img src="icon.png"/> | project</p>
  <span itemprop="programmingLanguage">Python</span>
  <a class="Link--muted" href="/octo-org/hello-world/stargazers">
    <svg></svg> 12,345
  </a>
  <a href="/octo-org/hello-world/forks"><svg></svg> 678</a>
  <span class="float-sm-right d-inline-block"><svg></svg> 1,234 stars this week</span>
</article>
</body></html>
"""


class ParseReposTests(unittest.TestCase):
    def test_parses_reordered_attributes_classes_and_nested_icons(self):
        repos = fetch_trending.parse_repos(TRENDING_HTML)

        self.assertEqual(1, len(repos))
        self.assertEqual("octo-org/hello-world", repos[0]["full_name"])
        self.assertEqual("A useful | project", repos[0]["description"])
        self.assertEqual("Python", repos[0]["language"])
        self.assertEqual("12345", repos[0]["total_stars"])
        self.assertEqual("678", repos[0]["forks"])
        self.assertEqual("1234", repos[0]["stars_week"])

    def test_ignores_non_repository_links(self):
        page = '<article class="Box-row"><h2><a href="/settings">Settings</a></h2></article>'
        self.assertEqual([], fetch_trending.parse_repos(page))


class GenerateReportTests(unittest.TestCase):
    def test_escapes_markdown_and_formats_stars(self):
        repos = fetch_trending.parse_repos(TRENDING_HTML)
        report = fetch_trending.generate_report(repos, date(2026, 7, 27), date(2026, 8, 2))

        self.assertIn("A useful \\| project", report)
        self.assertIn("| +1.2k |", report)
        self.assertTrue(report.endswith("*\n"))


class UpdateReadmeTests(unittest.TestCase):
    def test_replaces_only_latest_report_section(self):
        readme = """# Project

## 最新周报

<!-- LATEST_REPORT_START -->
旧内容
<!-- LATEST_REPORT_END -->

保留内容
"""
        updated = fetch_trending.update_latest_report(
            readme, date(2026, 7, 27), date(2026, 8, 2), "weekly/20260727-20260802.md"
        )

        self.assertIn(
            "[2026年07月27日—2026年08月02日](weekly/20260727-20260802.md)", updated
        )
        self.assertNotIn("旧内容", updated)
        self.assertIn("保留内容", updated)

    def test_raises_when_markers_are_missing(self):
        with self.assertRaisesRegex(ValueError, "LATEST_REPORT"):
            fetch_trending.update_latest_report(
                "# Project\n", date(2026, 7, 27), date(2026, 8, 2), "weekly/report.md"
            )


    def test_rolls_back_report_when_readme_write_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            report_path = Path(temp_dir) / "weekly" / "report.md"
            readme_path = Path(temp_dir) / "README.md"
            readme_path.write_text("old readme", encoding="utf-8")
            real_atomic_write = fetch_trending.atomic_write

            def fail_readme(path, content):
                if Path(path) == readme_path:
                    raise OSError("write failed")
                real_atomic_write(path, content)

            with patch.object(fetch_trending, "atomic_write", side_effect=fail_readme):
                with self.assertRaisesRegex(OSError, "write failed"):
                    fetch_trending.publish_report(report_path, "new report", readme_path, "new readme")

            self.assertFalse(report_path.exists())
            self.assertEqual("old readme", readme_path.read_text(encoding="utf-8"))


class MainTests(unittest.TestCase):
    def test_does_not_write_empty_report_when_parsing_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "empty.html"
            source.write_text("<html></html>", encoding="utf-8")
            output_dir = Path(temp_dir) / "weekly"
            with patch.object(fetch_trending.sys, "argv", ["fetch_trending.py", str(source)]), patch.object(
                fetch_trending, "OUTPUT_DIR", output_dir
            ):
                with self.assertRaisesRegex(RuntimeError, "未解析到任何仓库"):
                    fetch_trending.main()

            self.assertFalse(output_dir.exists())


if __name__ == "__main__":
    unittest.main()
