"""
PDF Generator - Playwright (Chromium)
Replaces WeasyPrint. Screen == PDF. Always.
"""
import os

# Set browser path before Playwright initialises
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', '/opt/render/project/src/.playwright')


def html_to_pdf(html_string):
    """Convert HTML string to PDF bytes using Playwright/Chromium."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("Playwright not installed")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
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
        browser.close()

    return pdf_bytes
