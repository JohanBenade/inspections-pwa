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
    
    # Get latest cycle for this unit (optional - can be passed as query param)
    from flask import request
    cycle_id = request.args.get('cycle')
    
    cycle = None
    if cycle_id:
        cycle = query_db("SELECT * FROM inspection_cycle WHERE id = ?", [cycle_id], one=True)
    else:
        # Get most recent inspection cycle for this unit
        latest = query_db("""
            SELECT ic.* FROM inspection i
            JOIN inspection_cycle ic ON i.cycle_id = ic.id
            WHERE i.unit_id = ?
            ORDER BY ic.cycle_number DESC LIMIT 1
        """, [unit_id], one=True)
        if latest:
            cycle = latest
            cycle_id = latest['id']
    
    # Generate PDF
    pdf_bytes = generate_defects_pdf(tenant_id, unit_id, cycle_id)
    
    if not pdf_bytes:
        abort(500, "Failed to generate PDF")
    
    # Generate filename
    insp = query_db("SELECT inspection_date FROM inspection WHERE unit_id = ? AND cycle_id = ?", [unit_id, cycle_id], one=True)
    insp_date = insp['inspection_date'] if insp else None
    filename = generate_pdf_filename(unit, cycle, inspection_date=insp_date)
    
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
    
    cycle = None
    if not cycle_id:
        latest = query_db("""
            SELECT ic.* FROM inspection i
            JOIN inspection_cycle ic ON i.cycle_id = ic.id
            WHERE i.unit_id = ?
            ORDER BY ic.cycle_number DESC LIMIT 1
        """, [unit_id], one=True)
        if latest:
            cycle_id = latest['id']
    
    # Generate PDF
    pdf_bytes = generate_defects_pdf(tenant_id, unit_id, cycle_id)
    
    if not pdf_bytes:
        abort(500, "Failed to generate PDF")
    
    # Build filename
    cycle_obj = None
    if cycle_id:
        cycle_obj = query_db("SELECT cycle_number FROM inspection_cycle WHERE id = ?", [cycle_id], one=True)
    insp = query_db("SELECT inspection_date FROM inspection WHERE unit_id = ? AND cycle_id = ?", [unit_id, cycle_id], one=True)
    insp_date = insp['inspection_date'] if insp else None
    filename = generate_pdf_filename(unit, cycle_obj, inspection_date=insp_date)

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
            "SELECT ic.* FROM inspection i"
            " JOIN inspection_cycle ic ON i.cycle_id = ic.id"
            " WHERE i.unit_id = ?"
            " ORDER BY ic.cycle_number DESC LIMIT 1",
            [unit_id], one=True
        )
        if latest:
            cycle_id = latest['id']

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
