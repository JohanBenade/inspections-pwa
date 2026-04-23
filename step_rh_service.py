import pathlib
path = pathlib.Path('app/services/pdf_playwright.py')
content = path.read_text()

old = '''def html_to_pdf(html_string, footer_template=None):
    """Convert HTML string to PDF bytes using Playwright/Chromium.
    Optional footer_template enables Playwright header/footer rendering.
    """
    browser = _get_browser()
    page = browser.new_page()
    try:
        page.set_content(html_string, wait_until='load')
        pdf_opts = {
            'format': 'A4',
            'print_background': True,
            'margin': {
                'top': '18mm',
                'bottom': '20mm',
                'left': '16mm',
                'right': '16mm',
            },
        }
        if footer_template:
            pdf_opts['display_header_footer'] = True
            pdf_opts['header_template'] = '<span></span>'
            pdf_opts['footer_template'] = footer_template
        pdf_bytes = page.pdf(**pdf_opts)
    finally:
        page.close()
    return pdf_bytes'''

new = '''def html_to_pdf(html_string, footer_template=None, header_template=None, margin=None):
    """Convert HTML string to PDF bytes using Playwright/Chromium.
    Optional header_template/footer_template enable Playwright running header/footer.
    Optional margin dict overrides defaults (e.g. when a header needs more top space).
    """
    browser = _get_browser()
    page = browser.new_page()
    try:
        page.set_content(html_string, wait_until='load')
        pdf_opts = {
            'format': 'A4',
            'print_background': True,
            'margin': margin or {
                'top': '18mm',
                'bottom': '20mm',
                'left': '16mm',
                'right': '16mm',
            },
        }
        if footer_template or header_template:
            pdf_opts['display_header_footer'] = True
            pdf_opts['header_template'] = header_template or '<span></span>'
            pdf_opts['footer_template'] = footer_template or '<span></span>'
        pdf_bytes = page.pdf(**pdf_opts)
    finally:
        page.close()
    return pdf_bytes'''

assert old in content, "html_to_pdf block not found"
content = content.replace(old, new)
path.write_text(content)
print("OK: service accepts header_template and margin")
