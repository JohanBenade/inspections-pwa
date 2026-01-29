"""
PDF Generator Service - Generates defects list PDFs.
Uses WeasyPrint for HTML to PDF conversion.
"""
import os
import io
from datetime import datetime
from flask import render_template, current_app
from app.services.db import query_db


def _get_weasyprint():
    """Lazy import weasyprint."""
    try:
        from weasyprint import HTML
        return HTML
    except ImportError:
        return None


def get_defects_data(tenant_id, unit_id, cycle_id=None):
    """
    Fetch all defects for a unit, optionally filtered by cycle.
    Returns structured data for PDF template.
    """
    # Get unit info
    unit = query_db("""
        SELECT u.*, ph.phase_name, ph.id as phase_id,
               p.project_name, p.id as project_id
        FROM unit u
        JOIN phase ph ON u.phase_id = ph.id
        JOIN project p ON ph.project_id = p.id
        WHERE u.id = ? AND u.tenant_id = ?
    """, [unit_id, tenant_id], one=True)
    
    if not unit:
        return None
    
    # Get cycle info if specified
    cycle = None
    cycle_number = 1
    if cycle_id:
        cycle = query_db("""
            SELECT * FROM inspection_cycle WHERE id = ?
        """, [cycle_id], one=True)
        if cycle:
            cycle_number = cycle['cycle_number']
    
    # Get all inspections for this unit up to current cycle
    inspections = []
    if cycle_id:
        inspections = query_db("""
            SELECT i.*, ic.cycle_number
            FROM inspection i
            JOIN inspection_cycle ic ON i.cycle_id = ic.id
            WHERE i.unit_id = ? AND i.tenant_id = ? AND ic.cycle_number <= ?
            ORDER BY ic.cycle_number ASC
        """, [unit_id, tenant_id, cycle_number])
    
    # Get latest inspection for this unit and cycle
    inspection_query = """
        SELECT i.*, ic.cycle_number
        FROM inspection i
        JOIN inspection_cycle ic ON i.cycle_id = ic.id
        WHERE i.unit_id = ? AND i.tenant_id = ?
    """
    params = [unit_id, tenant_id]
    
    if cycle_id:
        inspection_query += " AND i.cycle_id = ?"
        params.append(cycle_id)
    
    inspection_query += " ORDER BY ic.cycle_number DESC LIMIT 1"
    inspection = query_db(inspection_query, params, one=True)
    
    # Get ALL defects for this unit - both open and closed
    # We'll determine display status based on status and raised_cycle
    defect_query = """
        SELECT d.*, 
               it.item_description,
               parent.item_description as parent_description,
               ct.category_name, ct.category_order,
               at.area_name, at.area_order,
               ic_raised.cycle_number as raised_cycle,
               dh.comment as defect_comment
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at ON ct.area_id = at.id
        JOIN inspection_cycle ic_raised ON d.raised_cycle_id = ic_raised.id
        LEFT JOIN item_template parent ON it.parent_item_id = parent.id
        LEFT JOIN (
            SELECT defect_id, comment FROM defect_history 
            WHERE id IN (SELECT MIN(id) FROM defect_history GROUP BY defect_id)
        ) dh ON dh.defect_id = d.id
        WHERE d.unit_id = ? AND ic_raised.cycle_number <= ?
        ORDER BY at.area_order, ct.category_order, it.item_order
    """
    defect_params = [unit_id, cycle_number]
    
    defects = query_db(defect_query, defect_params)
    
    # Get area notes for this cycle
    area_notes = {}
    if cycle_id:
        notes = query_db("""
            SELECT can.note, at.area_name
            FROM cycle_area_note can
            JOIN area_template at ON can.area_template_id = at.id
            WHERE can.cycle_id = ?
        """, [cycle_id])
        area_notes = {n['area_name']: n['note'] for n in notes}
    
    # Get category comments for this unit
    category_comments = {}
    cat_notes = query_db("""
        SELECT cc.category_template_id, cch.comment as latest_comment,
               ct.category_name, at.area_name
        FROM category_comment cc
        LEFT JOIN category_comment_history cch ON cch.category_comment_id = cc.id
        JOIN category_template ct ON cc.category_template_id = ct.id
        JOIN area_template at ON ct.area_id = at.id
        WHERE cc.unit_id = ?
        ORDER BY cch.created_at DESC
    """, [unit_id])
    for c in cat_notes:
        key = (c['area_name'], c['category_name'])
        if key not in category_comments:
            category_comments[key] = c['latest_comment']
    
    # Get excluded items for this cycle - grouped by area
    excluded_by_area = {}
    if cycle_id:
        excluded = query_db("""
            SELECT it.item_description, ct.category_name, at.area_name, at.area_order,
                   cei.reason
            FROM cycle_excluded_item cei
            JOIN item_template it ON cei.item_template_id = it.id
            JOIN category_template ct ON it.category_id = ct.id
            JOIN area_template at ON ct.area_id = at.id
            WHERE cei.cycle_id = ?
            ORDER BY at.area_order, ct.category_order
        """, [cycle_id])
        for e in excluded:
            area_name = e['area_name']
            if area_name not in excluded_by_area:
                excluded_by_area[area_name] = []
            excluded_by_area[area_name].append(e['item_description'])
    
    # Structure defects by area -> category
    defects_by_area = {}
    defect_counter = 1
    
    # Summary counters
    total_rectified = 0
    total_not_rectified = 0
    total_new = 0
    
    for d in defects:
        area_name = d['area_name']
        cat_name = d['category_name']
        
        if area_name not in defects_by_area:
            defects_by_area[area_name] = {
                'name': area_name,
                'order': d['area_order'],
                'note': area_notes.get(area_name),
                'excluded_items': excluded_by_area.get(area_name, []),
                'categories': {}
            }
        
        if cat_name not in defects_by_area[area_name]['categories']:
            cat_note_key = (area_name, cat_name)
            defects_by_area[area_name]['categories'][cat_name] = {
                'name': cat_name,
                'order': d['category_order'],
                'note': category_comments.get(cat_note_key),
                'defects': []
            }
        
        # Build description with parent context
        description = d['item_description']
        if d['parent_description']:
            description = f"{d['parent_description']} - {description}"
        
        # Determine defect status for display
        raised_cycle = d['raised_cycle']
        status = d['status']
        
        if status == 'closed':
            # Rectified (at some point)
            display_status = 'rectified'
            total_rectified += 1
        elif status == 'open' and raised_cycle < cycle_number:
            # Open from previous cycle - not rectified
            display_status = 'not_rectified'
            total_not_rectified += 1
        elif status == 'open' and raised_cycle == cycle_number:
            # New defect this cycle
            display_status = 'new'
            total_new += 1
        else:
            display_status = 'open'
        
        defects_by_area[area_name]['categories'][cat_name]['defects'].append({
            'id': f"DEF-{defect_counter:03d}",
            'description': description,
            'comment': d['defect_comment'] or d['original_comment'],
            'type': d['defect_type'],
            'raised_cycle': raised_cycle,
            'display_status': display_status
        })
        defect_counter += 1
    
    # Convert to sorted list structure
    areas_list = []
    for area_name, area_data in sorted(defects_by_area.items(), key=lambda x: x[1]['order']):
        categories_list = []
        for cat_name, cat_data in sorted(area_data['categories'].items(), key=lambda x: x[1]['order']):
            categories_list.append({
                'name': cat_name,
                'note': cat_data.get('note'),
                'defects': cat_data['defects']
            })
        areas_list.append({
            'name': area_name,
            'note': area_data['note'],
            'excluded_items': area_data.get('excluded_items', []),
            'categories': categories_list
        })
    
    # Build inspection timeline
    inspection_timeline = []
    for insp in inspections:
        insp_date = None
        raw_date = insp['inspection_date'] if 'inspection_date' in insp.keys() else None
        if raw_date:
            try:
                dt = datetime.fromisoformat(str(raw_date).replace('Z', '+00:00'))
                insp_date = dt.strftime('%d.%m.%Y')
            except (ValueError, AttributeError):
                insp_date = str(raw_date)
        
        inspection_timeline.append({
            'cycle_number': insp['cycle_number'],
            'date': insp_date,
            'inspector': insp['inspector_name']
        })
    
    # Calculate summary
    total_defects = len(defects)
    total_excluded = sum(len(items) for items in excluded_by_area.values())
    
    # Format inspection date
    insp_date = None
    if inspection:
        raw_date = inspection['inspection_date'] if 'inspection_date' in inspection.keys() else None
        if raw_date:
            try:
                dt = datetime.fromisoformat(str(raw_date).replace('Z', '+00:00'))
                insp_date = dt.strftime('%d.%m.%Y')
            except (ValueError, AttributeError):
                insp_date = str(raw_date)
    
    return {
        'unit': unit,
        'project': {'project_name': unit['project_name']},
        'phase': {'phase_name': unit['phase_name']},
        'cycle': cycle,
        'cycle_number': cycle_number,
        'inspection': inspection,
        'inspection_timeline': inspection_timeline,
        'defects_by_area': areas_list,
        'summary': {
            'total': total_defects,
            'rectified': total_rectified,
            'not_rectified': total_not_rectified,
            'new': total_new,
            'excluded': total_excluded
        },
        'inspection_date': insp_date or datetime.now().strftime('%d.%m.%Y'),
        'inspector_name': inspection['inspector_name'] if inspection else 'N/A',
        'certification_date': None
    }


def generate_defects_pdf(tenant_id, unit_id, cycle_id=None):
    """
    Generate a defects list PDF for a unit.
    Returns PDF bytes or None if WeasyPrint unavailable.
    """
    HTML = _get_weasyprint()
    if HTML is None:
        return None
    
    # Get data
    data = get_defects_data(tenant_id, unit_id, cycle_id)
    if not data:
        return None
    
    # Get paths to static files
    static_folder = current_app.static_folder
    logo_path = os.path.join(static_folder, 'monograph_logo.jpg')
    signature_path = os.path.join(static_folder, 'kevin_signature.png')
    
    # Convert to file:// URLs for WeasyPrint
    logo_url = f"file://{logo_path}" if os.path.exists(logo_path) else ''
    signature_url = f"file://{signature_path}" if os.path.exists(signature_path) else ''
    
    # Render HTML template
    html_content = render_template(
        'pdf/defects_list.html',
        **data,
        logo_path=logo_url,
        signature_path=signature_url
    )
    
    # Generate PDF using WeasyPrint
    html_doc = HTML(string=html_content, base_url=static_folder)
    pdf_bytes = html_doc.write_pdf()
    
    return pdf_bytes


def generate_pdf_filename(unit, cycle=None):
    """Generate filename for PDF."""
    date_str = datetime.now().strftime('%Y%m%d')
    unit_num = unit['unit_number']
    
    if cycle:
        return f"DEFECTS_Unit_{unit_num}_Cycle_{cycle['cycle_number']}_{date_str}.pdf"
    return f"DEFECTS_Unit_{unit_num}_{date_str}.pdf"
