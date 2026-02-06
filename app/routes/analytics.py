"""
Analytics routes - Defect pattern dashboard for managers.
Provides data-driven view of defect patterns across all units in a cycle.
Access: Manager + Admin only.
"""
from flask import Blueprint, render_template, session, request
from app.auth import require_manager
from app.services.db import query_db

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')


# Area colour mapping (consistent across all charts)
AREA_COLOURS = {
    'KITCHEN': '#3b82f6',
    'BATHROOM': '#14b8a6',
    'BEDROOM A': '#a855f7',
    'BEDROOM B': '#6366f1',
    'BEDROOM C': '#ec4899',
    'BEDROOM D': '#f97316',
    'LOUNGE': '#22c55e',
}


@analytics_bp.route('/')
@require_manager
def dashboard():
    """Analytics Dashboard - defect patterns across all units in a cycle."""
    tenant_id = session['tenant_id']

    # Get available cycles for selector
    cycles = query_db("""
        SELECT id, cycle_number, unit_start, unit_end, status
        FROM inspection_cycle
        WHERE tenant_id = ?
        ORDER BY cycle_number DESC
    """, [tenant_id])

    # Determine active cycle (from query param or default to active/latest)
    selected_cycle_id = request.args.get('cycle')
    if not selected_cycle_id and cycles:
        active = [c for c in cycles if c['status'] == 'active']
        selected_cycle_id = active[0]['id'] if active else cycles[0]['id']

    if not selected_cycle_id:
        return render_template('analytics/dashboard.html',
                               cycles=[], selected_cycle_id=None,
                               has_data=False)

    # --- 1. SUMMARY STATS ---
    total_units = query_db("""
        SELECT COUNT(DISTINCT u.id)
        FROM unit u
        JOIN inspection i ON i.unit_id = u.id
        WHERE i.cycle_id = ? AND i.tenant_id = ?
    """, [selected_cycle_id, tenant_id], one=True)[0]

    total_defects = query_db("""
        SELECT COUNT(*)
        FROM defect d
        WHERE d.raised_cycle_id = ? AND d.tenant_id = ? AND d.status = 'open'
    """, [selected_cycle_id, tenant_id], one=True)[0]

    avg_defects = round(total_defects / total_units, 1) if total_units > 0 else 0

    unit_defect_counts = query_db("""
        SELECT u.unit_number, COUNT(*) as cnt
        FROM defect d
        JOIN unit u ON d.unit_id = u.id
        WHERE d.raised_cycle_id = ? AND d.tenant_id = ? AND d.status = 'open'
        GROUP BY d.unit_id
        ORDER BY cnt DESC
    """, [selected_cycle_id, tenant_id])

    worst_unit = unit_defect_counts[0] if unit_defect_counts else None
    best_unit = unit_defect_counts[-1] if unit_defect_counts else None
    min_defects = best_unit['cnt'] if best_unit else 0
    max_defects = worst_unit['cnt'] if worst_unit else 0

    summary = {
        'total_units': total_units,
        'total_defects': total_defects,
        'avg_defects': avg_defects,
        'min_defects': min_defects,
        'max_defects': max_defects,
        'worst_unit': worst_unit['unit_number'] if worst_unit else '-',
        'worst_count': worst_unit['cnt'] if worst_unit else 0,
    }

    # --- 2. DEFECTS BY AREA ---
    by_area = query_db("""
        SELECT at.area_name, COUNT(*) as cnt
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at ON ct.area_id = at.id
        WHERE d.raised_cycle_id = ? AND d.tenant_id = ? AND d.status = 'open'
        GROUP BY at.area_name
        ORDER BY cnt DESC
    """, [selected_cycle_id, tenant_id])

    area_data = {
        'labels': [r['area_name'] for r in by_area],
        'counts': [r['cnt'] for r in by_area],
        'colours': [AREA_COLOURS.get(r['area_name'], '#9ca3af') for r in by_area],
    }

    # --- 3. DEFECTS BY CATEGORY ---
    by_category = query_db("""
        SELECT ct.category_name, COUNT(*) as cnt
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        WHERE d.raised_cycle_id = ? AND d.tenant_id = ? AND d.status = 'open'
        GROUP BY ct.category_name
        ORDER BY cnt DESC
    """, [selected_cycle_id, tenant_id])

    category_data = {
        'labels': [r['category_name'].upper() for r in by_category],
        'counts': [r['cnt'] for r in by_category],
    }

    # --- 4. UNIT RANKING ---
    unit_ranking = query_db("""
        SELECT u.unit_number, u.id as unit_id, i.inspector_name, COUNT(d.id) as cnt
        FROM defect d
        JOIN unit u ON d.unit_id = u.id
        JOIN inspection i ON i.unit_id = u.id AND i.cycle_id = d.raised_cycle_id
        WHERE d.raised_cycle_id = ? AND d.tenant_id = ? AND d.status = 'open'
        GROUP BY u.unit_number, i.inspector_name
        ORDER BY cnt DESC
    """, [selected_cycle_id, tenant_id])

    # --- 5. HEATMAP: AREA x UNIT ---
    heatmap_raw = query_db("""
        SELECT u.unit_number, at.area_name, COUNT(*) as cnt
        FROM defect d
        JOIN unit u ON d.unit_id = u.id
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at ON ct.area_id = at.id
        WHERE d.raised_cycle_id = ? AND d.tenant_id = ? AND d.status = 'open'
        GROUP BY u.unit_number, at.area_name
    """, [selected_cycle_id, tenant_id])

    all_units_sorted = sorted(set(r['unit_number'] for r in heatmap_raw))
    all_areas = area_data['labels'] if area_data['labels'] else []

    heatmap = {}
    for r in heatmap_raw:
        if r['unit_number'] not in heatmap:
            heatmap[r['unit_number']] = {}
        heatmap[r['unit_number']][r['area_name']] = r['cnt']

    area_totals = {}
    for area in all_areas:
        area_totals[area] = sum(heatmap.get(u, {}).get(area, 0) for u in all_units_sorted)

    unit_totals = {}
    for u in all_units_sorted:
        unit_totals[u] = sum(heatmap.get(u, {}).values())

    # --- 6. RECURRING DEFECTS (3+ units) ---
    recurring = query_db("""
        SELECT d.original_comment, COUNT(*) as cnt,
               ct.category_name,
               GROUP_CONCAT(DISTINCT u.unit_number) as affected_units
        FROM defect d
        JOIN unit u ON d.unit_id = u.id
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        WHERE d.raised_cycle_id = ? AND d.tenant_id = ? AND d.status = 'open'
        GROUP BY d.original_comment
        HAVING COUNT(DISTINCT u.id) >= 3
        ORDER BY cnt DESC
    """, [selected_cycle_id, tenant_id])

    # --- 7. INSPECTOR PERFORMANCE ---
    inspector_stats = query_db("""
        SELECT i.inspector_name,
               COUNT(DISTINCT i.unit_id) as units_inspected,
               COUNT(d.id) as total_defects,
               ROUND(CAST(COUNT(d.id) AS FLOAT) / COUNT(DISTINCT i.unit_id), 1) as avg_per_unit
        FROM inspection i
        LEFT JOIN defect d ON d.unit_id = i.unit_id
            AND d.raised_cycle_id = i.cycle_id
            AND d.status = 'open'
        WHERE i.cycle_id = ? AND i.tenant_id = ?
        GROUP BY i.inspector_name
        ORDER BY avg_per_unit DESC
    """, [selected_cycle_id, tenant_id])

    selected_cycle = None
    for c in cycles:
        if c['id'] == selected_cycle_id:
            selected_cycle = c
            break

    return render_template('analytics/dashboard.html',
                           cycles=cycles,
                           selected_cycle_id=selected_cycle_id,
                           selected_cycle=selected_cycle,
                           has_data=total_units > 0,
                           summary=summary,
                           area_data=area_data,
                           category_data=category_data,
                           unit_ranking=unit_ranking,
                           all_units_sorted=all_units_sorted,
                           all_areas=all_areas,
                           heatmap=heatmap,
                           area_totals=area_totals,
                           unit_totals=unit_totals,
                           recurring=recurring,
                           inspector_stats=inspector_stats,
                           area_colours=AREA_COLOURS)

# ============================================================
# BI-WEEKLY REPORT ROUTES (v64g)
# ============================================================

def _to_dicts(rows):
    """Convert sqlite3.Row results to plain dicts."""
    return [dict(r) for r in rows]


def _to_dict(row):
    """Convert a single sqlite3.Row to a plain dict."""
    return dict(row) if row else None


@analytics_bp.route('/report/<cycle_id>')
@require_manager
def report_view(cycle_id):
    """Bi-weekly report - HTML preview (printable)."""
    data = _build_report_data(cycle_id)
    if data is None:
        return "Cycle not found", 404
    return render_template('analytics/report.html', is_pdf=False, **data)


@analytics_bp.route('/report/<cycle_id>/pdf')
@require_manager
def report_pdf(cycle_id):
    """Bi-weekly report - PDF download via WeasyPrint."""
    from weasyprint import HTML
    from flask import Response, request as req
    from datetime import datetime

    data = _build_report_data(cycle_id)
    if data is None:
        return "Cycle not found", 404

    html_str = render_template('analytics/report.html', is_pdf=True, **data)
    pdf_bytes = HTML(string=html_str, base_url=req.url_root).write_pdf()

    cycle = data['cycle']
    block = cycle.get('block') or 'Block'
    fname = "Monograph_Inspection_Report_Cycle{}_{}_{}_.pdf".format(
        cycle.get('cycle_number', 1), block.replace(' ', ''),
        datetime.utcnow().strftime('%Y%m%d')
    )

    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={'Content-Disposition': 'attachment; filename={}'.format(fname)}
    )


def _build_report_data(cycle_id):
    """Gather all data needed for the bi-weekly report.
    All query results are converted to plain dicts immediately
    to avoid sqlite3.Row immutability issues.
    """
    import base64, os
    from flask import current_app

    tenant_id = session['tenant_id']

    # --- Cycle info ---
    cycle = _to_dict(query_db("""
        SELECT id, cycle_number, block, floor, unit_start, unit_end,
               status, general_notes, exclusion_notes,
               request_received_date, started_at, created_at
        FROM inspection_cycle
        WHERE id = ? AND tenant_id = ?
    """, [cycle_id, tenant_id], one=True))

    if not cycle:
        return None

    # --- Items per unit ---
    total_templates = query_db("""
        SELECT COUNT(*) FROM item_template WHERE tenant_id = ?
    """, [tenant_id], one=True)[0]
    excluded_count = query_db("""
        SELECT COUNT(DISTINCT ii.item_template_id)
        FROM inspection_item ii
        JOIN inspection i ON ii.inspection_id = i.id
        WHERE i.cycle_id = ? AND i.tenant_id = ? AND ii.status = 'skipped'
    """, [cycle_id, tenant_id], one=True)[0]
    items_per_unit = total_templates - excluded_count if excluded_count > 0 else 438

    # --- Units with inspections in this cycle ---
    units = _to_dicts(query_db("""
        SELECT u.id, u.unit_number, u.block, u.floor, u.status as unit_status,
               i.id as insp_id, i.status as insp_status, i.inspector_name,
               i.inspection_date, i.started_at as insp_started,
               i.submitted_at, i.review_started_at, i.review_submitted_at, i.approved_at
        FROM unit u
        JOIN inspection i ON i.unit_id = u.id AND i.cycle_id = ?
        WHERE u.tenant_id = ?
        AND u.id NOT IN (SELECT unit_id FROM cycle_excluded_unit WHERE cycle_id = ?)
        ORDER BY u.unit_number
    """, [cycle_id, tenant_id, cycle_id]))

    total_units = len(units)
    if total_units == 0:
        return None

    # --- Defect counts per unit ---
    unit_defects = _to_dicts(query_db("""
        SELECT u.unit_number, u.id as unit_id, COUNT(d.id) as defect_count
        FROM unit u
        JOIN inspection i2 ON i2.unit_id = u.id AND i2.cycle_id = ?
        LEFT JOIN defect d ON d.unit_id = u.id AND d.raised_cycle_id = ? AND d.status = 'open'
        WHERE u.tenant_id = ?
        AND u.id NOT IN (SELECT unit_id FROM cycle_excluded_unit WHERE cycle_id = ?)
        GROUP BY u.id
        ORDER BY u.unit_number
    """, [cycle_id, cycle_id, tenant_id, cycle_id]))

    total_defects = sum(u['defect_count'] for u in unit_defects)
    avg_defects = round(total_defects / total_units, 1) if total_units > 0 else 0
    total_items = items_per_unit * total_units
    defect_rate = round((total_defects / total_items) * 100, 1) if total_items > 0 else 0

    # Median
    counts_sorted = sorted([u['defect_count'] for u in unit_defects])
    n = len(counts_sorted)
    if n % 2 == 0:
        median_defects = (counts_sorted[n // 2 - 1] + counts_sorted[n // 2]) / 2
    else:
        median_defects = counts_sorted[n // 2]

    # Certified count
    certified_count = sum(1 for u in units if u.get('unit_status') == 'certified')

    # --- Pipeline counts ---
    pipeline = {'not_started': 0, 'in_progress': 0, 'submitted': 0,
                'under_review': 0, 'reviewed': 0, 'approved': 0,
                'certified': 0, 'pending_followup': 0}
    for u in units:
        status = u.get('insp_status') or 'not_started'
        if status in pipeline:
            pipeline[status] += 1

    # --- Pipeline dates ---
    pipeline_dates = {}
    if cycle.get('request_received_date'):
        pipeline_dates['requested'] = cycle['request_received_date']
    insp_dates = [u['inspection_date'] for u in units if u.get('inspection_date')]
    if insp_dates:
        pipeline_dates['inspected'] = min(insp_dates)
    review_dates = [u['review_submitted_at'] for u in units if u.get('review_submitted_at')]
    if review_dates:
        pipeline_dates['reviewed'] = max(review_dates)[:10]
    approved_dates = [u['approved_at'] for u in units if u.get('approved_at')]
    if approved_dates:
        pipeline_dates['approved'] = max(approved_dates)[:10]

    # --- Defects by area ---
    area_data = _to_dicts(query_db("""
        SELECT at2.area_name as area, COUNT(d.id) as defect_count
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at2 ON ct.area_id = at2.id
        WHERE d.raised_cycle_id = ? AND d.tenant_id = ? AND d.status = 'open'
        GROUP BY at2.area_name
        ORDER BY defect_count DESC
    """, [cycle_id, tenant_id]))

    # Compute donut chart SVG data
    circumference = 439.82
    offset = 0
    for a in area_data:
        pct = a['defect_count'] / total_defects if total_defects > 0 else 0
        a['pct'] = round(pct * 100, 1)
        a['dash'] = round(pct * circumference, 2)
        a['offset'] = round(offset, 2)
        offset += a['dash']

    # --- Top defect types ---
    top_defects = _to_dicts(query_db("""
        SELECT original_comment as description, COUNT(*) as count
        FROM defect
        WHERE raised_cycle_id = ? AND tenant_id = ? AND status = 'open'
        GROUP BY original_comment
        ORDER BY count DESC
        LIMIT 10
    """, [cycle_id, tenant_id]))

    for d in top_defects:
        d['pct'] = round((d['count'] / total_defects) * 100, 1) if total_defects > 0 else 0

    # --- Unit table ---
    unit_map = {u['unit_number']: u for u in units}
    unit_table = []
    max_defects = max((u['defect_count'] for u in unit_defects), default=1)
    for ud in unit_defects:
        info = unit_map.get(ud['unit_number'], {})
        variance = ud['defect_count'] - avg_defects
        unit_rate = round((ud['defect_count'] / items_per_unit) * 100, 1) if items_per_unit > 0 else 0
        unit_table.append({
            'unit_number': ud['unit_number'],
            'block': info.get('block', cycle.get('block') or ''),
            'floor': info.get('floor', cycle.get('floor')),
            'inspector_name': info.get('inspector_name', ''),
            'defect_count': ud['defect_count'],
            'defect_rate': unit_rate,
            'variance': round(variance, 1),
            'insp_status': info.get('insp_status', 'not_started'),
            'bar_pct': round((ud['defect_count'] / max_defects) * 100, 1) if max_defects > 0 else 0,
        })

    # Floor display mapping
    floor_map = {0: 'Ground', 1: '1st', 2: '2nd', 3: '3rd'}

    # --- Load images as base64 ---
    logo_b64 = ''
    sig_b64 = ''
    try:
        img_dir = os.path.join(current_app.static_folder, 'images')
        logo_path = os.path.join(img_dir, 'monograph_logo.jpg')
        sig_path = os.path.join(img_dir, 'kc_signature.png')
        if os.path.exists(logo_path):
            with open(logo_path, 'rb') as f:
                logo_b64 = base64.b64encode(f.read()).decode()
        if os.path.exists(sig_path):
            with open(sig_path, 'rb') as f:
                sig_b64 = base64.b64encode(f.read()).decode()
    except Exception:
        pass

    # Area colours for report
    report_area_colours = ['#C8963E', '#3D6B8E', '#4A7C59', '#C44D3F', '#7B6B8D', '#5A8A7A', '#B07D4B']

    return {
        'cycle': cycle,
        'total_units': total_units,
        'total_defects': total_defects,
        'avg_defects': avg_defects,
        'median_defects': median_defects,
        'items_per_unit': items_per_unit,
        'total_items': total_items,
        'defect_rate': defect_rate,
        'certified_count': certified_count,
        'pipeline': pipeline,
        'pipeline_dates': pipeline_dates,
        'area_data': area_data,
        'top_defects': top_defects,
        'unit_table': unit_table,
        'max_defects': max_defects,
        'floor_map': floor_map,
        'logo_b64': logo_b64,
        'sig_b64': sig_b64,
        'area_colours': report_area_colours,
        'report_date': __import__('datetime').datetime.utcnow().strftime('%d %B %Y'),
    }
