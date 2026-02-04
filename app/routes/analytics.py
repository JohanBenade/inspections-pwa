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
