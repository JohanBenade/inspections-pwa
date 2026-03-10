"""
PDF Generator - Playwright (Chromium)
Replaces WeasyPrint. Screen == PDF. Always.
Persistent browser instance - launch once per process, reuse for all requests.
"""
import os

_playwright = None
_browser = None


def _get_browser():
    """Return persistent browser instance, launching if needed."""
    global _playwright, _browser
    if _browser is not None:
        return _browser
    from playwright.sync_api import sync_playwright
    _playwright = sync_playwright().start()
    _browser = _playwright.chromium.launch()
    return _browser


def html_to_pdf(html_string):
    """Convert HTML string to PDF bytes using Playwright/Chromium."""
    browser = _get_browser()
    page = browser.new_page()
    try:
        page.set_content(html_string, wait_until='networkidle')
        pdf_bytes = page.pdf(
            format='A4',
            print_background=True,
            margin={
                'top': '18mm',
                'bottom': '20mm',
                'left': '16mm',
                'right': '16mm'
            }
        )
    finally:
        page.close()
    return pdf_bytes
