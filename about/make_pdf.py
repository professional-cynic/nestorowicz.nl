#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: 2026 Toni Nestorowicz
# SPDX-License-Identifier: AGPL-3.0-or-later
# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright==1.56.0"]
# ///
"""Render the About me view of index.html as a one-page PDF CV.

The page's own print styles lay the CV out, and Chromium draws it exactly as a browser would,
but without the date, address and page numbers a browser adds when printing. The first run
downloads the Chromium build that Playwright drives (about 150 MB).

Usage:  ./make_pdf.py      (writes toni-nestorowicz-cv.pdf next to this script)
"""
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import Error, sync_playwright

HERE = Path(__file__).resolve().parent
PAGE = HERE.parent / "index.html"
OUT = HERE / "toni-nestorowicz-cv.pdf"


def main() -> None:
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Error:   # first run: fetch the browser
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
            browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(PAGE.as_uri() + "#about")
        page.evaluate("document.title = 'Toni Nestorowicz CV'")   # the title stored in the PDF
        page.pdf(path=OUT, format="A4", prefer_css_page_size=True)
        browser.close()
    print(f"CV written to {OUT}")


if __name__ == "__main__":
    main()
