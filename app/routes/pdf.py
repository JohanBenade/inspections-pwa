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
    filename = generate_pdf_filename(unit, cycle)
    
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
    
    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': 'inline'
        }
    )
