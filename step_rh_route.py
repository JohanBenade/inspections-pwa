import pathlib
path = pathlib.Path('app/routes/analytics.py')
content = path.read_text()

old = '''    data['is_pdf'] = True
    html_str = render_template('analytics/briefing.html', **data)
    pdf_bytes = html_to_pdf(html_str)
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    fname = 'PPSH_Site_Briefing_{}.pdf'.format(
        data['batch']['name'].replace(' ', '_'))'''

new = '''    data['is_pdf'] = True
    html_str = render_template('analytics/briefing.html', **data)
    batch_name = data['batch']['name']
    report_date = data.get('report_date', '')
    header_template = (
        '<div style="font-size: 8pt; color: #8F8E88; width: 100%; padding: 0 16mm; '
        'font-family: -apple-system, system-ui, sans-serif; '
        'display: flex; justify-content: space-between; align-items: baseline;">'
        '<span style="font-weight: 500; color: #4A4A4A;">' + batch_name + '</span>'
        '<span>' + report_date + ' &middot; Power Park Student Housing Phase 3</span>'
        '<span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>'
        '</div>'
    )
    pdf_margin = {'top': '22mm', 'bottom': '20mm', 'left': '16mm', 'right': '16mm'}
    pdf_bytes = html_to_pdf(html_str, header_template=header_template, margin=pdf_margin)
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    fname = 'PPSH_Site_Briefing_{}.pdf'.format(batch_name.replace(' ', '_'))'''

assert old in content, "batch_briefing_pdf block not found"
content = content.replace(old, new)
path.write_text(content)
print("OK: route passes running header and larger top margin")
