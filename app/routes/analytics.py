"""
Analytics routes - Defect pattern dashboard for managers.
Provides data-driven view of defect patterns across all units in a cycle.
Access: Manager + Admin only.
"""
from flask import Blueprint, render_template, session, request, make_response
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
    tenant_id = session.get('tenant_id', 'MONOGRAPH')

    # Get available cycles for selector
    cycles = query_db("""
        SELECT id, cycle_number, unit_start, unit_end, status, block, floor
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

    # --- ALL MODE: Project-wide aggregate view ---
    if selected_cycle_id == 'all':
        total_units = query_db(
            "SELECT COUNT(DISTINCT u.id) FROM unit u JOIN inspection i ON i.unit_id = u.id WHERE i.tenant_id = ?",
            [tenant_id], one=True)[0]
        total_defects = query_db(
            "SELECT COUNT(*) FROM defect WHERE tenant_id = ? AND status = 'open'",
            [tenant_id], one=True)[0]
        avg_defects = round(total_defects / total_units, 1) if total_units > 0 else 0

        unit_defect_counts = query_db(
            "SELECT u.unit_number, COUNT(*) as cnt FROM defect d JOIN unit u ON d.unit_id = u.id "
            "WHERE d.tenant_id = ? AND d.status = 'open' GROUP BY d.unit_id ORDER BY cnt DESC",
            [tenant_id])
        worst_unit = unit_defect_counts[0] if unit_defect_counts else None
        best_unit = unit_defect_counts[-1] if unit_defect_counts else None

        summary = {
            'total_units': total_units,
            'total_defects': total_defects,
            'avg_defects': avg_defects,
            'min_defects': best_unit['cnt'] if best_unit else 0,
            'max_defects': worst_unit['cnt'] if worst_unit else 0,
            'worst_unit': worst_unit['unit_number'] if worst_unit else '-',
            'worst_count': worst_unit['cnt'] if worst_unit else 0,
        }

        # Block comparison
        block_comparison = [dict(r) for r in query_db(
            "SELECT ic.block, COUNT(DISTINCT i.unit_id) as units, "
            "COUNT(d.id) as defects, "
            "ROUND(COUNT(d.id) * 1.0 / COUNT(DISTINCT i.unit_id), 1) as avg_per_unit "
            "FROM inspection_cycle ic "
            "JOIN inspection i ON i.cycle_id = ic.id "
            "LEFT JOIN defect d ON d.raised_cycle_id = ic.id AND d.unit_id = i.unit_id AND d.status = 'open' "
            "WHERE ic.tenant_id = ? GROUP BY ic.block ORDER BY ic.block",
            [tenant_id])]


        # Trend data (Block 5 vs Block 6 comparison)
        trend_data = {}
        if len(block_comparison) >= 2:
            b5 = block_comparison[0]
            b6 = block_comparison[1]
            avg_change = round(((b6["avg_per_unit"] - b5["avg_per_unit"]) / b5["avg_per_unit"]) * 100, 1) if b5["avg_per_unit"] > 0 else 0
            defect_change = round(((b6["defects"] - b5["defects"]) / b5["defects"]) * 100, 1) if b5["defects"] > 0 else 0
            trend_data = {
                "b5_avg": b5["avg_per_unit"], "b6_avg": b6["avg_per_unit"],
                "avg_change": avg_change,
                "b5_defects": b5["defects"], "b6_defects": b6["defects"],
                "defect_change": defect_change,
                "b5_units": b5["units"], "b6_units": b6["units"],
                "b5_label": b5["block"], "b6_label": b6["block"],
            }

        # Area breakdown by block (for grouped comparison chart)
        area_by_block_raw = query_db(
            "SELECT at2.area_name, ic.block, COUNT(*) as cnt "
            "FROM defect d "
            "JOIN item_template it ON d.item_template_id = it.id "
            "JOIN category_template ct ON it.category_id = ct.id "
            "JOIN area_template at2 ON ct.area_id = at2.id "
            "JOIN inspection_cycle ic ON d.raised_cycle_id = ic.id "
            "WHERE d.tenant_id = ? AND d.status = 'open' "
            "GROUP BY at2.area_name, ic.block ORDER BY at2.area_name",
            [tenant_id])
        # Build {area: {block: count}} structure
        area_by_block = {}
        block_labels = sorted(set(r["block"] for r in area_by_block_raw)) if area_by_block_raw else []
        for r in area_by_block_raw:
            if r["area_name"] not in area_by_block:
                area_by_block[r["area_name"]] = {}
            area_by_block[r["area_name"]][r["block"]] = r["cnt"]
        # Order areas by total descending
        area_compare_labels = sorted(area_by_block.keys(),
            key=lambda a: sum(area_by_block[a].values()), reverse=True)
        area_compare_data = {
            "labels": area_compare_labels,
            "block_labels": block_labels,
            "datasets": []
        }
        block_colours = {"Block 5": "#C8963E", "Block 6": "#3D6B8E"}
        for bl in block_labels:
            area_compare_data["datasets"].append({
                "label": bl,
                "colour": block_colours.get(bl, "#9ca3af"),
                "data": [area_by_block.get(a, {}).get(bl, 0) for a in area_compare_labels]
            })

        # Top defect types by block (for comparison table)
        defect_by_block_raw = query_db(
            "SELECT d.original_comment, ic.block, COUNT(*) as cnt "
            "FROM defect d "
            "JOIN inspection_cycle ic ON d.raised_cycle_id = ic.id "
            "WHERE d.tenant_id = ? AND d.status = 'open' "
            "GROUP BY d.original_comment, ic.block ORDER BY cnt DESC",
            [tenant_id])
        # Aggregate: {desc: {total, block5, block6}}
        defect_compare_map = {}
        for r in defect_by_block_raw:
            desc = r["original_comment"]
            if desc not in defect_compare_map:
                defect_compare_map[desc] = {"description": desc, "total": 0, "blocks": {}}
            defect_compare_map[desc]["total"] += r["cnt"]
            defect_compare_map[desc]["blocks"][r["block"]] = r["cnt"]
        defect_compare = sorted(defect_compare_map.values(), key=lambda x: x["total"], reverse=True)[:15]
        for d in defect_compare:
            d["block_labels"] = block_labels

        # Category breakdown by block (for grouped comparison chart)
        cat_by_block_raw = query_db(
            "SELECT ct.category_name, ic.block, COUNT(*) as cnt "
            "FROM defect d "
            "JOIN item_template it ON d.item_template_id = it.id "
            "JOIN category_template ct ON it.category_id = ct.id "
            "JOIN inspection_cycle ic ON d.raised_cycle_id = ic.id "
            "WHERE d.tenant_id = ? AND d.status = 'open' "
            "GROUP BY ct.category_name, ic.block ORDER BY cnt DESC",
            [tenant_id])
        cat_by_block = {}
        for r in cat_by_block_raw:
            name = r["category_name"].upper()
            if name not in cat_by_block:
                cat_by_block[name] = {}
            cat_by_block[name][r["block"]] = r["cnt"]
        cat_compare_labels = sorted(cat_by_block.keys(),
            key=lambda c: sum(cat_by_block[c].values()), reverse=True)
        cat_compare_data = {
            "labels": cat_compare_labels,
            "block_labels": block_labels,
            "datasets": []
        }
        for bl in block_labels:
            cat_compare_data["datasets"].append({
                "label": bl,
                "colour": block_colours.get(bl, "#9ca3af"),
                "data": [cat_by_block.get(c, {}).get(bl, 0) for c in cat_compare_labels]
            })

        # Area data
        by_area = query_db(
            "SELECT at.area_name, COUNT(*) as cnt "
            "FROM defect d JOIN item_template it ON d.item_template_id = it.id "
            "JOIN category_template ct ON it.category_id = ct.id "
            "JOIN area_template at ON ct.area_id = at.id "
            "WHERE d.tenant_id = ? AND d.status = 'open' "
            "GROUP BY at.area_name ORDER BY cnt DESC", [tenant_id])
        area_data = {
            'labels': [r['area_name'] for r in by_area],
            'counts': [r['cnt'] for r in by_area],
            'colours': [AREA_COLOURS.get(r['area_name'], '#9ca3af') for r in by_area],
        }

        # Category data
        by_category = query_db(
            "SELECT ct.category_name, COUNT(*) as cnt "
            "FROM defect d JOIN item_template it ON d.item_template_id = it.id "
            "JOIN category_template ct ON it.category_id = ct.id "
            "WHERE d.tenant_id = ? AND d.status = 'open' "
            "GROUP BY ct.category_name ORDER BY cnt DESC", [tenant_id])
        category_data = {
            'labels': [r['category_name'].upper() for r in by_category],
            'counts': [r['cnt'] for r in by_category],
        }

        # Unit ranking
        unit_ranking = query_db(
            "SELECT u.unit_number, u.id as unit_id, u.block, i.inspector_name, COUNT(d.id) as cnt "
            "FROM defect d JOIN unit u ON d.unit_id = u.id "
            "JOIN inspection i ON i.unit_id = u.id AND i.cycle_id = d.raised_cycle_id "
            "WHERE d.tenant_id = ? AND d.status = 'open' "
            "GROUP BY u.unit_number, i.inspector_name ORDER BY cnt DESC", [tenant_id])

        # Heatmap
        heatmap_raw = query_db(
            "SELECT u.unit_number, at.area_name, COUNT(*) as cnt "
            "FROM defect d JOIN unit u ON d.unit_id = u.id "
            "JOIN item_template it ON d.item_template_id = it.id "
            "JOIN category_template ct ON it.category_id = ct.id "
            "JOIN area_template at ON ct.area_id = at.id "
            "WHERE d.tenant_id = ? AND d.status = 'open' "
            "GROUP BY u.unit_number, at.area_name", [tenant_id])
        all_units_sorted = sorted(set(r['unit_number'] for r in heatmap_raw))
        all_areas = area_data['labels'] if area_data['labels'] else []
        heatmap = {}
        for r in heatmap_raw:
            if r['unit_number'] not in heatmap:
                heatmap[r['unit_number']] = {}
            heatmap[r['unit_number']][r['area_name']] = r['cnt']
        area_totals = {area: sum(heatmap.get(u, {}).get(area, 0) for u in all_units_sorted) for area in all_areas}
        unit_totals = {u: sum(heatmap.get(u, {}).values()) for u in all_units_sorted}

        # Recurring defects
        recurring = query_db(
            "SELECT d.original_comment, COUNT(*) as cnt, ct.category_name, "
            "GROUP_CONCAT(DISTINCT u.unit_number) as affected_units "
            "FROM defect d JOIN unit u ON d.unit_id = u.id "
            "JOIN item_template it ON d.item_template_id = it.id "
            "JOIN category_template ct ON it.category_id = ct.id "
            "WHERE d.tenant_id = ? AND d.status = 'open' "
            "GROUP BY d.original_comment HAVING COUNT(DISTINCT u.id) >= 3 "
            "ORDER BY cnt DESC", [tenant_id])

        # Inspector stats
        inspector_stats = query_db(
            "SELECT i.inspector_name, COUNT(DISTINCT i.unit_id) as units_inspected, "
            "COUNT(d.id) as total_defects, "
            "ROUND(CAST(COUNT(d.id) AS FLOAT) / COUNT(DISTINCT i.unit_id), 1) as avg_per_unit "
            "FROM inspection i LEFT JOIN defect d ON d.unit_id = i.unit_id "
            "AND d.raised_cycle_id = i.cycle_id AND d.status = 'open' "
            "WHERE i.tenant_id = ? GROUP BY i.inspector_name ORDER BY avg_per_unit DESC",
            [tenant_id])

        return render_template('analytics/dashboard.html',
            cycles=cycles, selected_cycle_id='all', selected_cycle=None,
            is_all_view=True, has_data=total_units > 0,
            context_header='Power Park Student Housing - Phase 3 | All Blocks | {} Units'.format(total_units),
            block_comparison=block_comparison,
            summary=summary, area_data=area_data, category_data=category_data,
            unit_ranking=unit_ranking, all_units_sorted=all_units_sorted,
            all_areas=all_areas, heatmap=heatmap, area_totals=area_totals,
            unit_totals=unit_totals, recurring=recurring,
            inspector_stats=inspector_stats, area_colours=AREA_COLOURS,
            trend_data=trend_data, area_compare_data=area_compare_data,
            defect_compare=defect_compare, cat_compare_data=cat_compare_data)

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

    # Build context header for per-cycle view
    ctx_block = selected_cycle['block'] if selected_cycle else ''
    ctx_units = '{}-{}'.format(selected_cycle['unit_start'], selected_cycle['unit_end']) if selected_cycle else ''
    context_header = 'Power Park Student Housing - Phase 3 | Cycle {} - {} | Units {}'.format(
        selected_cycle['cycle_number'] if selected_cycle else '?', ctx_block, ctx_units)

    return render_template('analytics/dashboard.html',
                           cycles=cycles,
                           selected_cycle_id=selected_cycle_id,
                           selected_cycle=selected_cycle,
                           is_all_view=False,
                           context_header=context_header,
                           block_comparison=None,
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



@analytics_bp.route('/reports')
@require_manager
def reports():
    """Reports listing - select a cycle to view/download report."""
    tenant_id = session.get('tenant_id', 'MONOGRAPH')
    cycles = query_db("""
        SELECT ic.id, ic.cycle_number, ic.block, ic.floor, ic.unit_start, ic.unit_end,
               ic.status, ic.request_received_date, ic.started_at,
               COUNT(DISTINCT i.unit_id) AS unit_count,
               COUNT(DISTINCT d.id) AS defect_count
        FROM inspection_cycle ic
        LEFT JOIN inspection i ON i.cycle_id = ic.id
        LEFT JOIN defect d ON d.raised_cycle_id = ic.id AND d.status = 'open'
        WHERE ic.tenant_id = ?
        GROUP BY ic.id
        ORDER BY ic.cycle_number DESC
    """, [tenant_id])
    cycles = [dict(r) for r in cycles]
    return render_template('analytics/reports.html', cycles=cycles)



@analytics_bp.route('/report/combined')
def combined_report_view(tenant_id=None):
    """Render combined bi-weekly report as HTML with toolbar."""
    data = _build_combined_report_data()
    if not data:
        flash('Not enough data for combined report (need 2+ blocks)', 'error')
        return redirect(url_for('analytics.reports'))
    data['is_pdf'] = False
    return render_template('analytics/report_combined.html', **data)


@analytics_bp.route('/report/combined/pdf')
def combined_report_pdf(tenant_id=None):
    """Generate combined bi-weekly report as PDF download."""
    from weasyprint import HTML
    data = _build_combined_report_data()
    if not data:
        flash('Not enough data for combined report', 'error')
        return redirect(url_for('analytics.reports'))
    data['is_pdf'] = True
    html_str = render_template('analytics/report_combined.html', **data)
    pdf_bytes = HTML(string=html_str, base_url=request.host_url).write_pdf()
    resp = make_response(pdf_bytes)
    resp.headers['Content-Type'] = 'application/pdf'
    resp.headers['Content-Disposition'] = 'attachment; filename=Combined_Inspection_Report_{}.pdf'.format(
        __import__('datetime').datetime.utcnow().strftime('%Y%m%d'))
    return resp


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


def _build_combined_report_data():
    """Gather data for combined bi-weekly report (all blocks/cycles).
    Returns dict with all template variables, or None if no data.
    All query results converted to plain dicts immediately.
    """
    import base64, os
    from flask import current_app

    tenant_id = session.get('tenant_id', 'MONOGRAPH')

    # --- Get all cycles ---
    cycles = [dict(r) for r in query_db("""
        SELECT id, cycle_number, block, floor, unit_start, unit_end, status, created_at
        FROM inspection_cycle WHERE tenant_id = ? ORDER BY block
    """, [tenant_id])]

    if len(cycles) < 2:
        return None

    # --- Per-block data ---
    blocks = {}
    for cyc in cycles:
        cid = cyc['id']
        block_name = cyc.get('block') or 'Unknown'

        units = [dict(r) for r in query_db("""
            SELECT u.id, u.unit_number, u.block, u.floor, u.status as unit_status,
                   i.id as insp_id, i.status as insp_status, i.inspector_name,
                   i.inspection_date
            FROM unit u
            JOIN inspection i ON i.unit_id = u.id AND i.cycle_id = ?
            WHERE u.tenant_id = ?
            ORDER BY u.unit_number
        """, [cid, tenant_id])]

        unit_defects = [dict(r) for r in query_db("""
            SELECT u.unit_number, u.id as unit_id, u.block, COUNT(d.id) as defect_count
            FROM unit u
            JOIN inspection i ON i.unit_id = u.id AND i.cycle_id = ?
            LEFT JOIN defect d ON d.unit_id = u.id AND d.raised_cycle_id = ? AND d.status = 'open'
            WHERE u.tenant_id = ?
            GROUP BY u.id ORDER BY u.unit_number
        """, [cid, cid, tenant_id])]

        total_units = len(units)
        total_defects = sum(u['defect_count'] for u in unit_defects)
        avg_defects = round(total_defects / total_units, 1) if total_units > 0 else 0

        # Items per unit (same for all cycles)
        total_templates = query_db(
            "SELECT COUNT(*) FROM item_template WHERE tenant_id = ?",
            [tenant_id], one=True)[0]
        excluded_count = query_db("""
            SELECT COUNT(DISTINCT ii.item_template_id)
            FROM inspection_item ii JOIN inspection i ON ii.inspection_id = i.id
            WHERE i.cycle_id = ? AND i.tenant_id = ? AND ii.status = 'skipped'
        """, [cid, tenant_id], one=True)[0]
        items_per_unit = total_templates - excluded_count if excluded_count > 0 else 438
        total_items = items_per_unit * total_units
        defect_rate = round((total_defects / total_items) * 100, 1) if total_items > 0 else 0

        insp_dates = [u['inspection_date'] for u in units if u.get('inspection_date')]
        insp_date_display = min(insp_dates)[:10] if insp_dates else None

        blocks[block_name] = {
            'block': block_name,
            'cycle_id': cid,
            'total_units': total_units,
            'total_defects': total_defects,
            'avg_defects': avg_defects,
            'items_per_unit': items_per_unit,
            'defect_rate': defect_rate,
            'unit_range': '{}-{}'.format(cyc.get('unit_start', ''), cyc.get('unit_end', '')),
            'inspection_date': insp_date_display,
            'units': units,
            'unit_defects': unit_defects,
        }

    # Identify B5 and B6
    block_names = sorted(blocks.keys())
    b5 = blocks.get(block_names[0], {})
    b6 = blocks.get(block_names[1], {})

    # --- Combined totals ---
    total_units = b5['total_units'] + b6['total_units']
    total_defects = b5['total_defects'] + b6['total_defects']
    avg_defects = round(total_defects / total_units, 1) if total_units > 0 else 0
    items_per_unit = b5['items_per_unit']
    total_items = items_per_unit * total_units
    defect_rate = round((total_defects / total_items) * 100, 1) if total_items > 0 else 0
    certified_count = sum(
        1 for bl in blocks.values()
        for u in bl['units'] if u.get('unit_status') == 'certified'
    )

    # --- Trend calculations ---
    avg_change = round(((b6['avg_defects'] - b5['avg_defects']) / b5['avg_defects']) * 100, 1) if b5['avg_defects'] > 0 else 0
    defect_change = round(((b6['total_defects'] - b5['total_defects']) / b5['total_defects']) * 100, 1) if b5['total_defects'] > 0 else 0
    rate_change = round(b6['defect_rate'] - b5['defect_rate'], 1)
    trend = {
        'avg_change': avg_change,
        'defect_change': defect_change,
        'rate_change': rate_change,
    }

    # --- Combined unit defects (sorted by unit number) ---
    all_unit_defects = []
    for bl in blocks.values():
        all_unit_defects.extend(bl['unit_defects'])
    all_unit_defects.sort(key=lambda x: x['unit_number'])
    max_defects = max((u['defect_count'] for u in all_unit_defects), default=1)

    # Worst unit
    worst_unit = max(all_unit_defects, key=lambda x: x['defect_count']) if all_unit_defects else {'unit_number': '-', 'defect_count': 0}
    high_defect_units = sum(1 for u in all_unit_defects if u['defect_count'] > 30)
    high_defect_pct = round((high_defect_units / total_units) * 100) if total_units > 0 else 0

    # --- Area data (combined + per-block) ---
    area_data_raw = [dict(r) for r in query_db("""
        SELECT at2.area_name as area, COUNT(d.id) as defect_count
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at2 ON ct.area_id = at2.id
        WHERE d.tenant_id = ? AND d.status = 'open'
        GROUP BY at2.area_name ORDER BY defect_count DESC
    """, [tenant_id])]

    # Compute donut SVG data
    circumference = 439.82
    offset = 0
    for a in area_data_raw:
        pct = a['defect_count'] / total_defects if total_defects > 0 else 0
        a['pct'] = round(pct * 100, 1)
        a['dash'] = round(pct * circumference, 2)
        a['offset'] = round(offset, 2)
        offset += a['dash']

    # Area comparison (per block)
    area_by_block_raw = [dict(r) for r in query_db("""
        SELECT at2.area_name as area, ic.block, COUNT(*) as cnt
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at2 ON ct.area_id = at2.id
        JOIN inspection_cycle ic ON d.raised_cycle_id = ic.id
        WHERE d.tenant_id = ? AND d.status = 'open'
        GROUP BY at2.area_name, ic.block ORDER BY cnt DESC
    """, [tenant_id])]

    area_block_map = {}
    for r in area_by_block_raw:
        if r['area'] not in area_block_map:
            area_block_map[r['area']] = {}
        area_block_map[r['area']][r['block']] = r['cnt']

    # Find max for bar scaling
    all_area_counts = []
    for area_counts in area_block_map.values():
        all_area_counts.extend(area_counts.values())
    max_area_count = max(all_area_counts) if all_area_counts else 1

    area_compare = []
    for a in area_data_raw:
        area_name = a['area']
        b5_count = area_block_map.get(area_name, {}).get(block_names[0], 0)
        b6_count = area_block_map.get(area_name, {}).get(block_names[1], 0)
        area_compare.append({
            'name': area_name,
            'b5_count': b5_count,
            'b6_count': b6_count,
            'b5_pct': round((b5_count / max_area_count) * 100, 1) if max_area_count > 0 else 0,
            'b6_pct': round((b6_count / max_area_count) * 100, 1) if max_area_count > 0 else 0,
        })

    # --- Top defect types comparison ---
    defect_by_block_raw = [dict(r) for r in query_db("""
        SELECT d.original_comment as description, ic.block, COUNT(*) as cnt
        FROM defect d
        JOIN inspection_cycle ic ON d.raised_cycle_id = ic.id
        WHERE d.tenant_id = ? AND d.status = 'open'
        GROUP BY d.original_comment, ic.block ORDER BY cnt DESC
    """, [tenant_id])]

    defect_map = {}
    for r in defect_by_block_raw:
        desc = r['description']
        if desc not in defect_map:
            defect_map[desc] = {'description': desc, 'total': 0, 'blocks': {}}
        defect_map[desc]['total'] += r['cnt']
        defect_map[desc]['blocks'][r['block']] = r['cnt']

    top_defects_compare = sorted(defect_map.values(), key=lambda x: x['total'], reverse=True)[:15]
    max_defect_total = top_defects_compare[0]['total'] if top_defects_compare else 1
    for d in top_defects_compare:
        d['b5_count'] = d['blocks'].get(block_names[0], 0)
        d['b6_count'] = d['blocks'].get(block_names[1], 0)
        d['bar_pct'] = round((d['total'] / max_defect_total) * 100, 1)

    # --- Unit summary table ---
    unit_table = []
    all_unit_map = {}
    for bl in blocks.values():
        for u in bl['units']:
            all_unit_map[u['unit_number']] = u

    for ud in all_unit_defects:
        info = all_unit_map.get(ud['unit_number'], {})
        variance = round(ud['defect_count'] - avg_defects, 1)
        unit_rate = round((ud['defect_count'] / items_per_unit) * 100, 1) if items_per_unit > 0 else 0
        unit_table.append({
            'unit_number': ud['unit_number'],
            'block': ud.get('block', info.get('block', '')),
            'inspector_name': info.get('inspector_name', ''),
            'defect_count': ud['defect_count'],
            'defect_rate': unit_rate,
            'variance': variance,
            'floor': info.get('floor', None),
            'insp_status': info.get('insp_status', 'not_started'),
        })

    # --- Compute median ---
    defect_counts_sorted = sorted([u['defect_count'] for u in unit_table])
    n_uts = len(defect_counts_sorted)
    if n_uts == 0:
        median_defects = 0
    elif n_uts % 2 == 0:
        median_defects = (defect_counts_sorted[n_uts // 2 - 1] + defect_counts_sorted[n_uts // 2]) / 2
    else:
        median_defects = defect_counts_sorted[n_uts // 2]
    median_defects = round(median_defects, 1)

    total_items = items_per_unit * total_units
    floor_map = {0: 'Ground', 1: '1st', 2: '2nd', 3: '3rd'}

    # --- Cycle options for report selector ---
    cycle_opts_rows = query_db(
        "SELECT id, cycle_number, block, unit_start, unit_end FROM inspection_cycle WHERE tenant_id=? ORDER BY block",
        [tenant], one=False
    )
    cycle_options = []
    if cycle_opts_rows:
        for cr in cycle_opts_rows:
            cr = dict(cr)
            label = "Cycle %s (%s - %s)" % (cr['cycle_number'], cr['unit_start'], cr['unit_end'])
            cycle_options.append({'id': cr['id'], 'label': label})

    # --- Load images as base64 ---
    logo_b64 = ''
    sig_b64 = ''
    try:
        img_dir = os.path.join(current_app.static_folder, 'images')
        logo_path = os.path.join(img_dir, 'monograph_logo.jpg')
        sig_path = os.path.join(img_dir, 'kc_signature.png')
        if os.path.exists(logo_path):
            with open(logo_path, 'rb') as fimg:
                logo_b64 = base64.b64encode(fimg.read()).decode()
        if os.path.exists(sig_path):
            with open(sig_path, 'rb') as fimg:
                sig_b64 = base64.b64encode(fimg.read()).decode()
    except Exception:
        pass

    area_colours = ['#C8963E', '#3D6B8E', '#4A7C59', '#C44D3F', '#7B6B8D', '#5A8A7A', '#B07D4B']

    return {
        'total_units': total_units,
        'total_defects': total_defects,
        'avg_defects': avg_defects,
        'items_per_unit': items_per_unit,
        'defect_rate': defect_rate,
        'certified_count': certified_count,
        'b5': b5,
        'b6': b6,
        'trend': trend,
        'area_data': area_data_raw,
        'area_compare': area_compare,
        'area_colours': area_colours,
        'top_defects_compare': top_defects_compare,
        'unit_defects': all_unit_defects,
        'max_defects': max_defects,
        'worst_unit': worst_unit,
        'high_defect_units': high_defect_units,
        'high_defect_pct': high_defect_pct,
        'unit_table': unit_table,
        'median_defects': median_defects,
        'total_items': total_items,
        'floor_map': floor_map,
        'cycle_options': cycle_options,
        'logo_b64': logo_b64,
        'sig_b64': sig_b64,
        'report_date': __import__('datetime').datetime.utcnow().strftime('%d %B %Y'),
    }


def _build_report_data(cycle_id):
    """Gather all data needed for the bi-weekly report.
    All query results are converted to plain dicts immediately
    to avoid sqlite3.Row immutability issues.
    """
    import base64, os
    from flask import current_app

    tenant_id = session.get('tenant_id', 'MONOGRAPH')

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

    # --- Cycle options for report selector ---
    cycle_opts_rows = query_db(
        "SELECT id, cycle_number, block, unit_start, unit_end FROM inspection_cycle WHERE tenant_id=? ORDER BY block",
        [tenant], one=False
    )
    cycle_options = []
    if cycle_opts_rows:
        for cr in cycle_opts_rows:
            cr = dict(cr)
            label = "Cycle %s (%s - %s)" % (cr['cycle_number'], cr['unit_start'], cr['unit_end'])
            cycle_options.append({'id': cr['id'], 'label': label})

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
        'cycle_options': cycle_options,
        'logo_b64': logo_b64,
        'sig_b64': sig_b64,
        'area_colours': report_area_colours,
        'report_date': __import__('datetime').datetime.utcnow().strftime('%d %B %Y'),
    }
