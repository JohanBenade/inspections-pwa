"""
PDF Generator - Playwright (Chromium)
Replaces WeasyPrint. Screen == PDF. Always.
"""
import os
import subprocess
import glob

BROWSERS_PATH = '/opt/render/project/src/data/.playwright'
os.environ['PLAYWRIGHT_BROWSERS_PATH'] = BROWSERS_PATH

_browser_ready = False


def _ensure_browser():
    """Install Chromium and system deps if not present. Runs once per process."""
    global _browser_ready
    if _browser_ready:
        return

    pattern = os.path.join(BROWSERS_PATH, 'chromium-*', 'chrome-linux', 'chrome')
    if not glob.glob(pattern):
        print("Playwright: installing Chromium...")
        result = subprocess.run(
            ['python', '-m', 'playwright', 'install', 'chromium'],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError("Playwright install failed: {}".format(result.stderr))
        print("Playwright: Chromium installed")

    # Install system deps - ignore non-zero exit (font packages unavailable on this OS)
    print("Playwright: installing system deps...")
    subprocess.run(
        ['python', '-m', 'playwright', 'install-deps', 'chromium'],
        capture_output=True, text=True
    )
    print("Playwright: system deps step complete")

    _browser_ready = True


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
