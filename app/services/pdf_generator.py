"""
PDF Generator Service - Generates defects list PDFs.
Uses WeasyPrint for HTML to PDF conversion.
"""
import os
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


def plain_text_to_html(text):
    """Convert plain text with line breaks to HTML paragraphs.
    If text already contains HTML tags, return as-is.
    """
    if not text:
        return text
    if '<' in text:
        return text
    lines = text.split('\n')
    return ''.join(
        '<p>{}</p>'.format(line.strip()) if line.strip() else '<p><br></p>'
        for line in lines
    )


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
        cycle = query_db("SELECT * FROM inspection_cycle WHERE id = ?", [cycle_id], one=True)
        if cycle:
            cycle_number = cycle['cycle_number']
    
    # Get all inspections for this unit up to current cycle
    inspections = []
    if cycle_id:
        inspections = query_db("""
            SELECT i.*, ic.cycle_number, ic.id as cycle_id
            FROM inspection i
            JOIN inspection_cycle ic ON i.cycle_id = ic.id
            WHERE i.unit_id = ? AND i.tenant_id = ? AND ic.cycle_number <= ?
            ORDER BY ic.cycle_number ASC
        """, [unit_id, tenant_id, cycle_number])
    
    # Get inspection for this unit and cycle
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
    
    # Get defects raised up to this cycle
    # Get comment from defect_history at or before this cycle (not latest!)
    defect_query = """
        SELECT d.*, 
               COALESCE(d.reviewed_comment, d.original_comment) AS display_comment,
               it.item_description,
               parent.item_description as parent_description,
               ct.category_name, ct.category_order,
               at.area_name, at.area_order,
               ic_raised.cycle_number as raised_cycle,
               ic_cleared.cycle_number as cleared_cycle,
               dh.comment as defect_comment
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at ON ct.area_id = at.id
        JOIN inspection_cycle ic_raised ON d.raised_cycle_id = ic_raised.id
        LEFT JOIN inspection_cycle ic_cleared ON d.cleared_cycle_id = ic_cleared.id
        LEFT JOIN item_template parent ON it.parent_item_id = parent.id
        LEFT JOIN (
            SELECT dh1.defect_id, dh1.comment 
            FROM defect_history dh1
            JOIN inspection_cycle ic ON dh1.cycle_id = ic.id
            WHERE ic.cycle_number <= ?
            AND dh1.id = (
                SELECT dh2.id FROM defect_history dh2
                JOIN inspection_cycle ic2 ON dh2.cycle_id = ic2.id
                WHERE dh2.defect_id = dh1.defect_id AND ic2.cycle_number <= ?
                ORDER BY ic2.cycle_number DESC LIMIT 1
            )
        ) dh ON dh.defect_id = d.id
        WHERE d.unit_id = ? AND ic_raised.cycle_number <= ?
        ORDER BY at.area_order, ct.category_order, it.item_order
    """
    defects = query_db(defect_query, [cycle_number, cycle_number, unit_id, cycle_number])
    
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
    
    # Get category comments for this unit AT OR BEFORE this cycle
    category_comments = {}
    cat_notes = query_db("""
        SELECT cc.category_template_id, cch.comment as latest_comment,
               ct.category_name, at.area_name
        FROM category_comment cc
        JOIN category_comment_history cch ON cch.category_comment_id = cc.id
        JOIN inspection_cycle ic ON cch.cycle_id = ic.id
        JOIN category_template ct ON cc.category_template_id = ct.id
        JOIN area_template at ON ct.area_id = at.id
        WHERE cc.unit_id = ? AND ic.cycle_number <= ?
        AND cch.id = (
            SELECT cch2.id FROM category_comment_history cch2
            JOIN inspection_cycle ic2 ON cch2.cycle_id = ic2.id
            WHERE cch2.category_comment_id = cc.id AND ic2.cycle_number <= ?
            ORDER BY ic2.cycle_number DESC LIMIT 1
        )
    """, [unit_id, cycle_number, cycle_number])
    for c in cat_notes:
        key = (c['area_name'], c['category_name'])
        if key not in category_comments:
            category_comments[key] = c['latest_comment']
    
    # Get excluded items count for summary (not for listing in PDF)
    excluded_count = 0
    if cycle_id:
        count_row = query_db(
            "SELECT COUNT(*) as cnt FROM cycle_excluded_item WHERE cycle_id = ?",
            [cycle_id], one=True
        )
        excluded_count = count_row['cnt'] if count_row else 0
    
    # Structure defects by area -> category
    defects_by_area = {}
    defect_counter = 1
    
    # Summary counters
    total_rectified = 0
    total_not_rectified = 0
    total_new = 0
    
    # Track defect counts per cycle for timeline
    cycle_stats = {}
    
    for d in defects:
        area_name = d['area_name']
        cat_name = d['category_name']
        
        if area_name not in defects_by_area:
            defects_by_area[area_name] = {
                'name': area_name,
                'order': d['area_order'],
                'note': area_notes.get(area_name),
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
            description = '{} - {}'.format(d['parent_description'], description)
        
        # Determine defect status for display
        raised_cycle = d['raised_cycle']
        cleared_cycle = d['cleared_cycle']
        status = d['status']
        
        # Track stats per cycle
        if raised_cycle not in cycle_stats:
            cycle_stats[raised_cycle] = {'raised': 0, 'rectified': 0}
        cycle_stats[raised_cycle]['raised'] += 1
        
        if cleared_cycle and cleared_cycle <= cycle_number:
            if cleared_cycle not in cycle_stats:
                cycle_stats[cleared_cycle] = {'raised': 0, 'rectified': 0}
            cycle_stats[cleared_cycle]['rectified'] += 1
        
        # Determine display status based on state AT this cycle
        was_cleared = cleared_cycle and cleared_cycle <= cycle_number
        
        if was_cleared and cleared_cycle == cycle_number:
            display_status = 'rectified'
            total_rectified += 1
        elif was_cleared and cleared_cycle < cycle_number:
            continue
        elif raised_cycle < cycle_number:
            display_status = 'not_rectified'
            total_not_rectified += 1
        elif raised_cycle == cycle_number:
            display_status = 'new'
            total_new += 1
        else:
            display_status = 'open'
            if cycle_number == 1:
                total_new += 1
        
        defects_by_area[area_name]['categories'][cat_name]['defects'].append({
            'id': 'DEF-{:03d}'.format(defect_counter),
            'description': description,
            'comment': (d['defect_comment'] or d['display_comment']) 
                       if (d['defect_comment'] or '').lower() not in ['rectified', 'fixed'] 
                       else d['display_comment'],
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
            if cat_data['defects']:
                categories_list.append({
                    'name': cat_name,
                    'note': cat_data.get('note'),
                    'defects': cat_data['defects']
                })
        if categories_list or area_data.get('note'):
            areas_list.append({
                'name': area_name,
                'note': area_data['note'],
                'categories': categories_list
            })
    
    # Calculate grand totals across all cycles
    grand_total_raised = sum(stats['raised'] for stats in cycle_stats.values())
    grand_total_rectified = sum(stats['rectified'] for stats in cycle_stats.values())
    
    # Determine if unit is certified (no outstanding defects)
    is_certified = (total_not_rectified == 0 and total_new == 0 and cycle_number > 1)
    
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
        
        insp_cycle_num = insp['cycle_number']
        stats = cycle_stats.get(insp_cycle_num, {'raised': 0, 'rectified': 0})
        
        total_raised_to_cycle = sum(
            cycle_stats.get(c, {'raised': 0})['raised'] 
            for c in range(1, insp_cycle_num + 1)
        )
        total_rectified_to_cycle = sum(
            cycle_stats.get(c, {'rectified': 0})['rectified'] 
            for c in range(1, insp_cycle_num + 1)
        )
        outstanding = total_raised_to_cycle - total_rectified_to_cycle
        
        inspection_timeline.append({
            'cycle_number': insp_cycle_num,
            'date': insp_date,
            'inspector': insp['inspector_name'],
            'raised': stats['raised'],
            'rectified': stats['rectified'],
            'outstanding': outstanding
        })
    
    # Calculate summary
    total_defects = total_rectified + total_not_rectified + total_new
    
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
    
    # Certification date is inspection date if certified
    certification_date = insp_date if is_certified else None
    
    # Get total inspection items for Cycle 1 summary
    total_items = 0
    if inspection:
        item_count = query_db(
            "SELECT COUNT(*) as cnt FROM inspection_item WHERE inspection_id = ?",
            [inspection['id']], one=True
        )
        total_items = item_count['cnt'] if item_count else 0
    
    inspection_summary = {
        'total': total_items,
        'excluded': excluded_count,
        'inspected': total_items - excluded_count,
        'defects': total_new if cycle_number == 1 else total_defects
    }
    
    # Process notes for PDF rendering (convert plain text to HTML if needed)
    general_notes_html = None
    exclusion_notes_html = None
    if cycle:
        gn = cycle['general_notes']
        if gn:
            general_notes_html = plain_text_to_html(gn)
        try:
            en = cycle['exclusion_notes']
            if en:
                exclusion_notes_html = plain_text_to_html(en)
        except (IndexError, KeyError):
            pass
    
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
            'excluded': excluded_count
        },
        'grand_totals': {
            'raised': grand_total_raised,
            'rectified': grand_total_rectified
        },
        'inspection_summary': inspection_summary,
        'is_certified': is_certified,
        'inspection_date': insp_date or datetime.now().strftime('%d.%m.%Y'),
        'inspection_date_raw': raw_date or '',
        'inspector_name': inspection['inspector_name'] if inspection else 'N/A',
        'certification_date': certification_date,
        'general_notes_html': general_notes_html,
        'exclusion_notes_html': exclusion_notes_html
    }


def generate_defects_pdf(tenant_id, unit_id, cycle_id=None):
    """Generate a defects list PDF for a unit."""
    HTML = _get_weasyprint()
    if HTML is None:
        return None
    
    data = get_defects_data(tenant_id, unit_id, cycle_id)
    if not data:
        return None
    
    static_folder = current_app.static_folder
    logo_path = os.path.join(static_folder, 'monograph_logo.jpg')
    signature_path = os.path.join(static_folder, 'kevin_signature.png')
    
    logo_url = 'file://{}'.format(logo_path) if os.path.exists(logo_path) else ''
    signature_url = 'file://{}'.format(signature_path) if os.path.exists(signature_path) else ''
    
    html_content = render_template(
        'pdf/defects_list.html',
        **data,
        logo_path=logo_url,
        signature_path=signature_url
    )
    
    html_doc = HTML(string=html_content, base_url=static_folder)
    pdf_bytes = html_doc.write_pdf()
    
    return pdf_bytes


def generate_pdf_filename(unit, cycle=None, inspection_date=None):
    """Generate filename matching Word doc naming: XXX_UNIT_INSPECTION 01_20260127.pdf"""
    unit_num = unit['unit_number']
    cycle_num = '01'
    if cycle:
        cycle_num = '{:02d}'.format(cycle['cycle_number'])
    if inspection_date:
        date_str = inspection_date.replace('-', '')
    else:
        date_str = datetime.now().strftime('%Y%m%d')
    return '{}_UNIT_INSPECTION {}_{}.pdf'.format(unit_num, cycle_num, date_str)
