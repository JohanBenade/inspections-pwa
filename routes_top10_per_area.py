@analytics_bp.route('/build-quality')
@require_team_lead
def top10_per_area_view():
    """Top 10 Defects per Area - C1 build-quality brief (HTML preview)."""
    import datetime, base64, os as _os
    from flask import current_app
    data = _build_top10_per_area_data()
    data['is_pdf'] = False
    data['report_date'] = datetime.datetime.now().strftime('%d %B %Y')
    logo_path = _os.path.join(current_app.static_folder, 'monograph_logo.jpg')
    if _os.path.exists(logo_path):
        with open(logo_path, 'rb') as f:
            data['logo_b64'] = base64.b64encode(f.read()).decode()
    else:
        data['logo_b64'] = ''
    return render_template('analytics/top_10_per_area.html', **data)


@analytics_bp.route('/build-quality/pdf')
@require_team_lead
def top10_per_area_pdf():
    """Top 10 Defects per Area - C1 build-quality brief (PDF download)."""
    from app.services.pdf_playwright import html_to_pdf
    import datetime, base64, os as _os
    from flask import current_app, make_response
    data = _build_top10_per_area_data()
    data['is_pdf'] = True
    data['report_date'] = datetime.datetime.now().strftime('%d %B %Y')
    logo_path = _os.path.join(current_app.static_folder, 'monograph_logo.jpg')
    if _os.path.exists(logo_path):
        with open(logo_path, 'rb') as f:
            data['logo_b64'] = base64.b64encode(f.read()).decode()
    else:
        data['logo_b64'] = ''
    html_str = render_template('analytics/top_10_per_area.html', **data)
    pdf_bytes = html_to_pdf(html_str)
    resp = make_response(pdf_bytes)
    resp.headers['Content-Type'] = 'application/pdf'
    today_iso = datetime.datetime.now().strftime('%Y-%m-%d')
    resp.headers['Content-Disposition'] = 'attachment; filename=Top10_Defects_Per_Area_{}.pdf'.format(today_iso)
    return resp
