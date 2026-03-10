"""
PDF Generator - Playwright (Chromium)
Replaces WeasyPrint. Screen == PDF. Always.
Chromium installs to persistent disk on first use.
"""
import os
import subprocess

BROWSERS_PATH = '/opt/render/project/src/data/.playwright'
os.environ['PLAYWRIGHT_BROWSERS_PATH'] = BROWSERS_PATH


def _ensure_browser():
    """Install Chromium if not present. Runs once on first use."""
    import glob
    pattern = os.path.join(BROWSERS_PATH, 'chromium-*', 'chrome-linux', 'chrome')
    matches = glob.glob(pattern)
    if not matches:
        print("Playwright: Chromium not found - installing to persistent disk...")
        result = subprocess.run(
            ['python', '-m', 'playwright', 'install', 'chromium'],
            capture_output=True, text=True
        )
        print("Playwright install stdout:", result.stdout)
        print("Playwright install stderr:", result.stderr)
        if result.returncode != 0:
            raise RuntimeError("Playwright install failed: {}".format(result.stderr))
        print("Playwright: Chromium installed successfully")


def html_to_pdf(html_string):
    """Convert HTML string to PDF bytes using Playwright/Chromium."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("Playwright not installed")

    _ensure_browser()

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
