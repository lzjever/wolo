#!/usr/bin/env python3
"""Open 163.com in a browser and save a screenshot."""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="163-home.png",
        help="Screenshot output path (default: 163-home.png)",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browser in headed mode (default: headless)",
    )
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        page = browser.new_page()
        last_error: Exception | None = None
        for url in ("https://www.163.com", "http://www.163.com"):
            try:
                page.goto(url, wait_until="load", timeout=60000)
                break
            except PlaywrightError as e:
                last_error = e
        else:
            browser.close()
            raise RuntimeError(f"Failed to open 163.com: {last_error}") from last_error
        page.wait_for_load_state("networkidle", timeout=60000)
        page.screenshot(path=str(output), full_page=True)
        browser.close()

    print(f"Screenshot saved to: {output}")


if __name__ == "__main__":
    main()
