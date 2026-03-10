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

# Ubuntu 24.04 package names (t64 suffix for 64-bit transition)
CHROMIUM_DEPS = [
    'libnss3', 'libnspr4', 'libdbus-1-3',
    'libatk1.0-0t64', 'libatk-bridge2.0-0t64',
    'libcups2t64', 'libdrm2', 'libatspi2.0-0t64',
    'libxcomposite1', 'libxdamage1', 'libxfixes3',
    'libxrandr2', 'libgbm1', 'libxkbcommon0', 'libasound2t64'
]


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

    print("Playwright: updating apt and installing system deps...")
    subprocess.run(['apt-get', 'update', '-qq'], capture_output=True, text=True)
    result = subprocess.run(
        ['apt-get', 'install', '-y'] + CHROMIUM_DEPS,
        capture_output=True, text=True
    )
    print("apt stdout:", result.stdout[-500:] if result.stdout else '')
    print("apt stderr:", result.stderr[-500:] if result.stderr else '')
    if result.returncode != 0:
        raise RuntimeError("apt-get install failed: {}".format(result.stderr))
    print("Playwright: system deps installed")

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
