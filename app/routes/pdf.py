"""
PDF routes - Generate and download PDF reports.
"""
from flask import Blueprint, session, abort, Response
from app.auth import require_team_lead
from app.services.db import query_db
from app.services.pdf_generator import generate_defects_pdf, generate_pdf_filename

pdf_bp = Blueprint('pdf', __name__, url_prefix='/pdf')


@pdf_bp.route('/defects/<unit_id>')
@require_team_lead
def download_defects_pdf(unit_id):
    """Generate and download defects list PDF for a unit."""
    tenant_id = session['tenant_id']
    
    # Get unit
    unit = query_db(
        "SELECT * FROM unit WHERE id = ? AND tenant_id = ?",
        [unit_id, tenant_id], one=True
    )
    if not unit:
        abort(404)
    
    # Get cycle from inspection record
    from flask import request
    cycle_id = request.args.get('cycle')
    
    if cycle_id:
        insp = query_db("SELECT * FROM inspection WHERE unit_id = ? AND cycle_id = ? AND tenant_id = ?",
                        [unit_id, cycle_id, tenant_id], one=True)
    else:
        insp = query_db("SELECT * FROM inspection WHERE unit_id = ? AND tenant_id = ? ORDER BY cycle_number DESC LIMIT 1",
                        [unit_id, tenant_id], one=True)
        if insp:
            cycle_id = insp['cycle_id']
    
    # Generate PDF
    pdf_bytes = generate_defects_pdf(tenant_id, unit_id, cycle_id)
    
    if not pdf_bytes:
        abort(500, "Failed to generate PDF")
    
    # Generate filename
    insp_date = insp['inspection_date'] if insp else None
    filename = generate_pdf_filename(unit, insp, inspection_date=insp_date)
    
    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
    )


@pdf_bp.route('/defects/<unit_id>/preview')
@require_team_lead
def preview_defects_pdf(unit_id):
    """Preview defects list PDF in browser (inline)."""
    tenant_id = session['tenant_id']
    
    # Get unit
    unit = query_db(
        "SELECT * FROM unit WHERE id = ? AND tenant_id = ?",
        [unit_id, tenant_id], one=True
    )
    if not unit:
        abort(404)
    
    # Get cycle
    from flask import request
    cycle_id = request.args.get('cycle')
    
    if not cycle_id:
        insp = query_db("SELECT * FROM inspection WHERE unit_id = ? AND tenant_id = ? ORDER BY cycle_number DESC LIMIT 1",
                        [unit_id, tenant_id], one=True)
        if insp:
            cycle_id = insp['cycle_id']
    else:
        insp = query_db("SELECT * FROM inspection WHERE unit_id = ? AND cycle_id = ? AND tenant_id = ?",
                        [unit_id, cycle_id, tenant_id], one=True)
    
    # Generate PDF
    pdf_bytes = generate_defects_pdf(tenant_id, unit_id, cycle_id)
    
    if not pdf_bytes:
        abort(500, "Failed to generate PDF")
    
    # Build filename
    insp_date = insp['inspection_date'] if insp else None
    filename = generate_pdf_filename(unit, insp, inspection_date=insp_date)

    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'inline; filename="{filename}"'
        }
    )


@pdf_bp.route('/defects/<unit_id>/view')
@require_team_lead
def view_defects_html(unit_id):
    """View defects list as HTML with print/download toolbar."""
    tenant_id = session['tenant_id']
    from flask import request as req, render_template, url_for
    from app.services.pdf_generator import get_defects_data

    unit = query_db(
        "SELECT * FROM unit WHERE id = ? AND tenant_id = ?",
        [unit_id, tenant_id], one=True
    )
    if not unit:
        abort(404)

    cycle_id = req.args.get('cycle')
    if not cycle_id:
        latest = query_db(
            "SELECT * FROM inspection WHERE unit_id = ? AND tenant_id = ? ORDER BY cycle_number DESC LIMIT 1",
            [unit_id, tenant_id], one=True
        )
        if latest:
            cycle_id = latest['cycle_id']

    data = get_defects_data(tenant_id, unit_id, cycle_id)
    if not data:
        abort(404)

    return render_template(
        'pdf/defects_list.html',
        **data,
        is_pdf=False,
        logo_path=url_for('static', filename='monograph_logo.jpg'),
        signature_path=url_for('static', filename='kevin_signature.png'),
        download_url=url_for('pdf.download_defects_pdf', unit_id=unit_id, cycle=cycle_id)
    )


@pdf_bp.route('/test-playwright')
@require_team_lead
def test_playwright_pdf():
    """Phase 1 test: confirm Playwright generates PDF on Render. Remove after Phase 1 sign-off."""
    from app.services.pdf_playwright import html_to_pdf
    html = """<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
body { font-family: sans-serif; padding: 40px; }
h1 { color: #1A1A1A; }
p { color: #6B6B6B; }
</style>
</head>
<body>
<h1>Playwright PDF Test</h1>
<p>If you can read this, Playwright is working correctly on Render.</p>
<p>Screen == PDF. WeasyPrint migration can proceed.</p>
</body></html>"""
    try:
        pdf_bytes = html_to_pdf(html)
        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={'Content-Disposition': 'attachment; filename=playwright_test.pdf'}
        )
    except Exception as e:
        return 'Playwright error: {}'.format(str(e)), 500
