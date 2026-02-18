"""
Analytics routes - Defect pattern dashboard for managers.
Provides data-driven view of defect patterns across all units in a cycle.
Access: Manager + Admin only.
"""
from flask import Blueprint, render_template, session, request, make_response
from app.auth import require_manager
import math
from app.services.db import query_db

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')


# Area colour mapping (consistent across all charts)
AREA_COLOURS = {
    'KITCHEN': '#C8963E',
    'BATHROOM': '#3D6B8E',
    'BEDROOM A': '#4A7C59',
    'BEDROOM D': '#C44D3F',
    'BEDROOM C': '#7B6B8D',
    'BEDROOM B': '#5A8A7A',
    'LOUNGE': '#B07D4B',
}

# Batch colours (assigned by order: 1st batch = gold, 2nd = blue, 3rd = green, etc.)
BATCH_COLOURS = ['#C8963E', '#3D6B8E', '#4A7C59', '#C44D3F', '#7B6B8D', '#5A8A7A', '#B07D4B']
FLOOR_LABELS = {0: 'Ground', 1: '1st Floor', 2: '2nd Floor', 3: '3rd Floor'}

# SQL fragment for batch label (used in GROUP BY queries)
BATCH_LABEL_SQL = ("(ic.block || ' ' || CASE ic.floor "
                   "WHEN 0 THEN 'Ground' WHEN 1 THEN '1st Floor' "
                   "WHEN 2 THEN '2nd Floor' WHEN 3 THEN '3rd Floor' "
                   "ELSE 'Floor ' || ic.floor END)")


@analytics_bp.route('/')
@require_manager
def dashboard():
    """Analytics Dashboard - defect patterns across all units in a cycle."""
    tenant_id = session.get('tenant_id', 'MONOGRAPH')

    # Get available cycles for selector
    cycles = query_db("""
        SELECT id, cycle_number, unit_start, unit_end, status, block, floor
        FROM inspection_cycle
        WHERE tenant_id = ? AND id NOT LIKE 'test-%'
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
            "SELECT COUNT(DISTINCT u.id) FROM unit u JOIN inspection i ON i.unit_id = u.id WHERE i.tenant_id = ? AND i.cycle_id NOT LIKE 'test-%'",
            [tenant_id], one=True)[0]
        total_defects = query_db(
            "SELECT COUNT(*) FROM defect WHERE tenant_id = ? AND status = 'open' AND raised_cycle_id NOT LIKE 'test-%'",
            [tenant_id], one=True)[0]
        avg_defects = round(total_defects / total_units, 1) if total_units > 0 else 0

        unit_defect_counts = query_db(
            "SELECT u.unit_number, COUNT(*) as cnt FROM defect d JOIN unit u ON d.unit_id = u.id "
            "WHERE d.tenant_id = ? AND d.status = 'open' AND d.raised_cycle_id NOT LIKE 'test-%' GROUP BY d.unit_id ORDER BY cnt DESC",
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

        # Batch comparison (per-cycle, not per-block)
        batch_comparison = [dict(r) for r in query_db(
            "SELECT ic.id as cycle_id, ic.block, ic.floor, "
            "COUNT(DISTINCT i.unit_id) as units, "
            "COUNT(d.id) as defects, "
            "ROUND(COUNT(d.id) * 1.0 / COUNT(DISTINCT i.unit_id), 1) as avg_per_unit, "
            "ic.unit_start, ic.unit_end, ic.created_at "
            "FROM inspection_cycle ic "
            "JOIN inspection i ON i.cycle_id = ic.id "
            "LEFT JOIN defect d ON d.raised_cycle_id = ic.id AND d.unit_id = i.unit_id AND d.status = 'open' "
            "WHERE ic.tenant_id = ? AND ic.id NOT LIKE 'test-%' "
            "GROUP BY ic.id ORDER BY ic.block, ic.floor",
            [tenant_id])]

        # Enrich batches with labels, colours, rates
        for idx, b in enumerate(batch_comparison):
            floor_label = FLOOR_LABELS.get(b.get('floor'), 'Floor {}'.format(b.get('floor', '?')))
            b['label'] = '{} {}'.format(b['block'], floor_label)
            b['colour'] = BATCH_COLOURS[idx % len(BATCH_COLOURS)]
            b['defect_rate'] = round(b['defects'] / (437 * b['units']) * 100, 1) if b['units'] > 0 else 0
            b['unit_range'] = '{}-{}'.format(b.get('unit_start', ''), b.get('unit_end', ''))
            b['inspection_date'] = b['created_at'][:10] if b.get('created_at') else '-'

        batch_labels = [b['label'] for b in batch_comparison]
        batch_colours = {b['label']: b['colour'] for b in batch_comparison}
        # Keep block_comparison as alias for template compatibility
        block_comparison = batch_comparison

        # Trend data (per-batch summaries for KPI cards)
        trend_data = {'batches': []}
        for b in batch_comparison:
            trend_data['batches'].append({
                'label': b['label'],
                'colour': b['colour'],
                'units': b['units'],
                'defects': b['defects'],
                'avg': b['avg_per_unit'],
            })

        # Area breakdown by batch (for grouped comparison chart)
        area_by_batch_raw = query_db(
            "SELECT at2.area_name, " + BATCH_LABEL_SQL + " as batch_label, COUNT(*) as cnt "
            "FROM defect d "
            "JOIN item_template it ON d.item_template_id = it.id "
            "JOIN category_template ct ON it.category_id = ct.id "
            "JOIN area_template at2 ON ct.area_id = at2.id "
            "JOIN inspection_cycle ic ON d.raised_cycle_id = ic.id "
            "WHERE d.tenant_id = ? AND d.status = 'open' AND ic.id NOT LIKE 'test-%' "
            "GROUP BY at2.area_name, batch_label ORDER BY at2.area_name",
            [tenant_id])
        # Build {area: {batch_label: count}} structure
        area_by_batch = {}
        for r in area_by_batch_raw:
            if r["area_name"] not in area_by_batch:
                area_by_batch[r["area_name"]] = {}
            area_by_batch[r["area_name"]][r["batch_label"]] = r["cnt"]
        # Order areas by total descending
        area_compare_labels = sorted(area_by_batch.keys(),
            key=lambda a: sum(area_by_batch[a].values()), reverse=True)
        area_compare_data = {
            "labels": area_compare_labels,
            "block_labels": batch_labels,
            "datasets": []
        }
        for bl in batch_labels:
            area_compare_data["datasets"].append({
                "label": bl,
                "colour": batch_colours.get(bl, "#9ca3af"),
                "data": [area_by_batch.get(a, {}).get(bl, 0) for a in area_compare_labels]
            })

        # Top defect types by batch (for comparison table)
        defect_by_batch_raw = query_db(
            "SELECT d.original_comment, " + BATCH_LABEL_SQL + " as batch_label, COUNT(*) as cnt "
            "FROM defect d "
            "JOIN inspection_cycle ic ON d.raised_cycle_id = ic.id "
            "WHERE d.tenant_id = ? AND d.status = 'open' AND ic.id NOT LIKE 'test-%' "
            "GROUP BY d.original_comment, batch_label ORDER BY cnt DESC",
            [tenant_id])
        # Aggregate: {desc: {total, batches: {label: count}}}
        defect_compare_map = {}
        for r in defect_by_batch_raw:
            desc = r["original_comment"]
            if desc not in defect_compare_map:
                defect_compare_map[desc] = {"description": desc, "total": 0, "batches": {}}
            defect_compare_map[desc]["total"] += r["cnt"]
            defect_compare_map[desc]["batches"][r["batch_label"]] = r["cnt"]
        defect_compare = sorted(defect_compare_map.values(), key=lambda x: x["total"], reverse=True)[:10]
        for d in defect_compare:
            d["batch_labels"] = batch_labels
            d["batch_colours"] = batch_colours

        # Category breakdown by batch (for grouped comparison chart)
        cat_by_batch_raw = query_db(
            "SELECT ct.category_name, " + BATCH_LABEL_SQL + " as batch_label, COUNT(*) as cnt "
            "FROM defect d "
            "JOIN item_template it ON d.item_template_id = it.id "
            "JOIN category_template ct ON it.category_id = ct.id "
            "JOIN inspection_cycle ic ON d.raised_cycle_id = ic.id "
            "WHERE d.tenant_id = ? AND d.status = 'open' AND ic.id NOT LIKE 'test-%' "
            "GROUP BY ct.category_name, batch_label ORDER BY cnt DESC",
            [tenant_id])
        cat_by_batch = {}
        for r in cat_by_batch_raw:
            name = r["category_name"].upper()
            if name not in cat_by_batch:
                cat_by_batch[name] = {}
            cat_by_batch[name][r["batch_label"]] = r["cnt"]
        cat_compare_labels = sorted(cat_by_batch.keys(),
            key=lambda c: sum(cat_by_batch[c].values()), reverse=True)
        cat_compare_data = {
            "labels": cat_compare_labels,
            "block_labels": batch_labels,
            "datasets": []
        }
        for bl in batch_labels:
            cat_compare_data["datasets"].append({
                "label": bl,
                "colour": batch_colours.get(bl, "#9ca3af"),
                "data": [cat_by_batch.get(c, {}).get(bl, 0) for c in cat_compare_labels]
            })

        # Area data
        by_area = query_db(
            "SELECT at.area_name, COUNT(*) as cnt "
            "FROM defect d JOIN item_template it ON d.item_template_id = it.id "
            "JOIN category_template ct ON it.category_id = ct.id "
            "JOIN area_template at ON ct.area_id = at.id "
            "WHERE d.tenant_id = ? AND d.status = 'open' AND d.raised_cycle_id NOT LIKE 'test-%' "
            "GROUP BY at.area_name ORDER BY cnt DESC", [tenant_id])
        area_data = {
            'labels': [r['area_name'] for r in by_area],
            'counts': [r['cnt'] for r in by_area],
            'colours': [AREA_COLOURS.get(r['area_name'], '#9ca3af') for r in by_area],
        }
        max_area_count = by_area[0]['cnt'] if by_area else 1
        area_list = []
        for r in by_area:
            area_list.append({
                'area': r['area_name'],
                'count': r['cnt'],
                'pct': round(r['cnt'] / total_defects * 100, 1) if total_defects > 0 else 0,
                'bar_pct': round(r['cnt'] / max_area_count * 100),
                'colour': AREA_COLOURS.get(r['area_name'], '#9ca3af'),
            })

        # Category data
        by_category = query_db(
            "SELECT ct.category_name, COUNT(*) as cnt "
            "FROM defect d JOIN item_template it ON d.item_template_id = it.id "
            "JOIN category_template ct ON it.category_id = ct.id "
            "WHERE d.tenant_id = ? AND d.status = 'open' AND d.raised_cycle_id NOT LIKE 'test-%' "
            "GROUP BY ct.category_name ORDER BY cnt DESC", [tenant_id])
        category_data = {
            'labels': [r['category_name'].upper() for r in by_category],
            'counts': [r['cnt'] for r in by_category],
        }
        max_cat_count = by_category[0]['cnt'] if by_category else 1
        category_list = []
        for r in by_category:
            name = r['category_name'].upper()
            category_list.append({
                'category': name,
                'count': r['cnt'],
                'pct': round(r['cnt'] / total_defects * 100, 1) if total_defects > 0 else 0,
                'bar_pct': round(r['cnt'] / max_cat_count * 100),
                'batch_counts': {bl: cat_by_batch.get(name, {}).get(bl, 0) for bl in batch_labels},
            })
        cat_counts_sorted = sorted([c['count'] for c in category_list])
        if not cat_counts_sorted:
            cat_median = 0
        elif len(cat_counts_sorted) % 2 == 0:
            cat_median = round((cat_counts_sorted[len(cat_counts_sorted)//2-1] + cat_counts_sorted[len(cat_counts_sorted)//2]) / 2, 1)
        else:
            cat_median = cat_counts_sorted[len(cat_counts_sorted)//2]

        unit_ranking = query_db(
            "SELECT u.unit_number, u.id as unit_id, u.block, i.inspector_name, COUNT(d.id) as cnt "
            "FROM defect d JOIN unit u ON d.unit_id = u.id "
            "JOIN inspection i ON i.unit_id = u.id AND i.cycle_id = d.raised_cycle_id "
            "WHERE d.tenant_id = ? AND d.status = 'open' AND d.raised_cycle_id NOT LIKE 'test-%' "
            "GROUP BY u.unit_number, i.inspector_name ORDER BY cnt DESC", [tenant_id])

        # Block/Floor grid (replaces item-level heatmap in all-view)
        all_areas = area_data['labels'] if area_data['labels'] else []
        grid_blocks = sorted(set(b['block'] for b in batch_comparison))
        grid_floors = sorted(set(b.get('floor', 0) for b in batch_comparison))
        block_floor_grid = {}
        for b in batch_comparison:
            blk = b['block']
            flr = b.get('floor', 0)
            if blk not in block_floor_grid:
                block_floor_grid[blk] = {}
            block_floor_grid[blk][flr] = {
                'avg': b['avg_per_unit'],
                'defects': b['defects'],
                'units': b['units'],
                'defect_rate': b.get('defect_rate', 0),
                'label': b['label'],
                'colour': b['colour'],
            }
        grid_avgs = []
        for blk in block_floor_grid.values():
            for cell in blk.values():
                if cell['units'] > 0:
                    grid_avgs.append(cell['avg'])
        if grid_avgs:
            grid_avgs_sorted = sorted(grid_avgs)
            n = len(grid_avgs_sorted)
            grid_median = grid_avgs_sorted[n // 2] if n % 2 == 1 else round((grid_avgs_sorted[n // 2 - 1] + grid_avgs_sorted[n // 2]) / 2, 1)
        else:
            grid_median = 0
        # Empty heatmap vars (per-cycle view uses these, all-view does not)
        heatmap = {}
        all_units_sorted = []
        area_totals = {}
        unit_totals = {}

        # Recurring defects
        recurring = query_db(
            "SELECT d.original_comment, COUNT(*) as cnt, ct.category_name, "
            "GROUP_CONCAT(DISTINCT u.unit_number) as affected_units "
            "FROM defect d JOIN unit u ON d.unit_id = u.id "
            "JOIN item_template it ON d.item_template_id = it.id "
            "JOIN category_template ct ON it.category_id = ct.id "
            "WHERE d.tenant_id = ? AND d.status = 'open' AND d.raised_cycle_id NOT LIKE 'test-%' "
            "GROUP BY d.original_comment HAVING COUNT(DISTINCT u.id) >= 3 "
            "ORDER BY cnt DESC", [tenant_id])

        # Inspector stats
        inspector_stats = query_db(
            "SELECT i.inspector_name, COUNT(DISTINCT i.unit_id) as units_inspected, "
            "COUNT(d.id) as total_defects, "
            "ROUND(CAST(COUNT(d.id) AS FLOAT) / COUNT(DISTINCT i.unit_id), 1) as avg_per_unit "
            "FROM inspection i LEFT JOIN defect d ON d.unit_id = i.unit_id "
            "AND d.raised_cycle_id = i.cycle_id AND d.status = 'open' "
            "WHERE i.tenant_id = ? AND i.cycle_id NOT LIKE 'test-%' GROUP BY i.inspector_name ORDER BY avg_per_unit DESC",
            [tenant_id])

        # Defect rate
        items_inspected = 437 * total_units
        defect_rate = round(total_defects / items_inspected * 100, 1) if items_inspected > 0 else 0
        summary['defect_rate'] = defect_rate
        summary['items_inspected'] = items_inspected

        # Certified count
        certified_count = query_db(
            "SELECT COUNT(*) FROM inspection WHERE tenant_id = ? AND status = 'certified' AND cycle_id NOT LIKE 'test-%'",
            [tenant_id], one=True)[0]
        summary['certified_count'] = certified_count

        # Median defects per unit
        counts_list = sorted([r['cnt'] for r in unit_defect_counts]) if unit_defect_counts else []
        if not counts_list:
            median_defects = 0
        elif len(counts_list) % 2 == 0:
            median_defects = round((counts_list[len(counts_list)//2-1] + counts_list[len(counts_list)//2]) / 2, 1)
        else:
            median_defects = counts_list[len(counts_list)//2]
        summary['median_defects'] = median_defects

        # Batch medians (for colour coding)
        batch_defect_counts = sorted([b['defects'] for b in batch_comparison]) if batch_comparison else []
        if not batch_defect_counts:
            batch_defects_median = 0
        elif len(batch_defect_counts) % 2 == 0:
            batch_defects_median = round((batch_defect_counts[len(batch_defect_counts)//2-1] + batch_defect_counts[len(batch_defect_counts)//2]) / 2, 1)
        else:
            batch_defects_median = batch_defect_counts[len(batch_defect_counts)//2]
        batch_rates = sorted([b['defect_rate'] for b in batch_comparison]) if batch_comparison else []
        if not batch_rates:
            batch_rate_median = 0
        elif len(batch_rates) % 2 == 0:
            batch_rate_median = round((batch_rates[len(batch_rates)//2-1] + batch_rates[len(batch_rates)//2]) / 2, 1)
        else:
            batch_rate_median = batch_rates[len(batch_rates)//2]

        # Inspector median
        insp_avgs = sorted([r['avg_per_unit'] for r in inspector_stats]) if inspector_stats else []
        if not insp_avgs:
            inspector_median = 0
        elif len(insp_avgs) % 2 == 0:
            inspector_median = round((insp_avgs[len(insp_avgs)//2-1] + insp_avgs[len(insp_avgs)//2]) / 2, 1)
        else:
            inspector_median = insp_avgs[len(insp_avgs)//2]

        floor_map = {0: 'Ground', 1: '1st', 2: '2nd', 3: '3rd'}

        # Pipeline: count inspections by mapped status
        pipeline_raw = query_db(
            "SELECT i.status, COUNT(*) as cnt FROM inspection i "
            "WHERE i.tenant_id = ? AND i.cycle_id NOT LIKE 'test-%' "
            "GROUP BY i.status", [tenant_id])
        pipe_counts = {r['status']: r['cnt'] for r in pipeline_raw}
        pipeline_total = sum(pipe_counts.values()) or 1
        pipeline_data = [
            {'label': 'Requested', 'count': pipe_counts.get('not_started', 0),
             'pct': round(pipe_counts.get('not_started', 0) / pipeline_total * 100)},
            {'label': 'Inspected', 'count': sum(pipe_counts.get(s, 0) for s in ['in_progress', 'submitted', 'reviewed']),
             'pct': round(sum(pipe_counts.get(s, 0) for s in ['in_progress', 'submitted', 'reviewed']) / pipeline_total * 100)},
            {'label': 'Issued to Site', 'count': sum(pipe_counts.get(s, 0) for s in ['approved', 'certified', 'pending_followup']),
             'pct': round(sum(pipe_counts.get(s, 0) for s in ['approved', 'certified', 'pending_followup']) / pipeline_total * 100)},
        ]
        # All-view: no specific dates
        for step in pipeline_data:
            step['date'] = ''

        # Top defect types (all-view)
        top_defects = query_db(
            "SELECT d.original_comment as description, COUNT(*) as cnt "
            "FROM defect d WHERE d.tenant_id = ? AND d.status = 'open' "
            "AND d.raised_cycle_id NOT LIKE 'test-%' "
            "GROUP BY d.original_comment ORDER BY cnt DESC LIMIT 10", [tenant_id])
        td_counts = sorted([r['cnt'] for r in top_defects]) if top_defects else []
        if not td_counts:
            td_median = 0
        elif len(td_counts) % 2 == 0:
            td_median = round((td_counts[len(td_counts)//2-1] + td_counts[len(td_counts)//2]) / 2, 1)
        else:
            td_median = td_counts[len(td_counts)//2]

        # Unit summary with 2-status
        unit_summary_raw = query_db(
            "SELECT u.unit_number, u.block, u.floor, i.status as insp_status, "
            "COUNT(d.id) as defect_count "
            "FROM inspection i JOIN unit u ON i.unit_id = u.id "
            "LEFT JOIN defect d ON d.unit_id = u.id AND d.status = 'open' "
            "AND d.raised_cycle_id = i.cycle_id "
            "WHERE i.tenant_id = ? AND i.cycle_id NOT LIKE 'test-%' "
            "GROUP BY u.unit_number, u.block, u.floor, i.status ORDER BY u.unit_number",
            [tenant_id])
        unit_summary = []
        for r in unit_summary_raw:
            s = r['insp_status']
            display_status = 'Issued to Site' if s in ('approved', 'certified', 'pending_followup') else 'Inspected'
            unit_summary.append({
                'unit_number': r['unit_number'], 'block': r['block'],
                'floor': r['floor'],
                'status': display_status, 'defect_count': r['defect_count'],
                'defect_rate': round(r['defect_count'] / 437 * 100, 1),
            })
        unit_summary.sort(key=lambda x: x['defect_count'], reverse=True)

        # Area Deep Dive: top 3 defect types for top 2 areas (with batch breakdown)
        deep_dive_raw = query_db(
            "SELECT at2.area_name, d.original_comment, "
            "" + BATCH_LABEL_SQL + " as batch_label, COUNT(*) as cnt "
            "FROM defect d "
            "JOIN item_template it ON d.item_template_id = it.id "
            "JOIN category_template ct ON it.category_id = ct.id "
            "JOIN area_template at2 ON ct.area_id = at2.id "
            "JOIN inspection_cycle ic ON d.raised_cycle_id = ic.id "
            "WHERE d.tenant_id = ? AND d.status = 'open' AND ic.id NOT LIKE 'test-%' "
            "GROUP BY at2.area_name, d.original_comment, batch_label "
            "ORDER BY at2.area_name, cnt DESC",
            [tenant_id])
        # Build {area: {desc: {total, batches}}}
        dd_map = {}
        dd_area_totals = {}
        for r in deep_dive_raw:
            area = r['area_name']
            desc = r['original_comment']
            if area not in dd_map:
                dd_map[area] = {}
                dd_area_totals[area] = 0
            if desc not in dd_map[area]:
                dd_map[area][desc] = {'total': 0, 'batches': {}}
            dd_map[area][desc]['total'] += r['cnt']
            dd_map[area][desc]['batches'][r['batch_label']] = r['cnt']
            dd_area_totals[area] += r['cnt']
        # Top 2 areas by total
        top_areas = sorted(dd_area_totals.keys(), key=lambda a: dd_area_totals[a], reverse=True)[:2]
        dd_colours = ['#C8963E', '#3D6B8E']
        area_deep_dive = []
        for idx, area in enumerate(top_areas):
            descs = dd_map[area]
            top_descs = sorted(descs.items(), key=lambda x: x[1]['total'], reverse=True)[:3]
            max_count = top_descs[0][1]['total'] if top_descs else 1
            defect_list = []
            for desc, info in top_descs:
                defect_list.append({
                    'description': desc,
                    'count': info['total'],
                    'pct': round(info['total'] / dd_area_totals[area] * 100, 1),
                    'bar_pct': round(info['total'] / max_count * 100),
                    'batch_counts': {bl: info['batches'].get(bl, 0) for bl in batch_labels},
                })
            area_deep_dive.append({
                'area': area,
                'total': dd_area_totals[area],
                'pct_of_total': round(dd_area_totals[area] / total_defects * 100, 1) if total_defects > 0 else 0,
                'colour': dd_colours[idx],
                'defects': defect_list,
            })

        # Deep dive callout
        dd_callout = ''
        if len(area_deep_dive) >= 1 and area_deep_dive[0]['defects']:
            a1 = area_deep_dive[0]
            d1 = a1['defects'][0]
            dd_callout = 'The most frequent defect in {} is {} ({} occurrences).'.format(
                a1['area'], d1['description'].lower(), d1['count'])
            if len(area_deep_dive) >= 2 and area_deep_dive[1]['defects']:
                a2 = area_deep_dive[1]
                d2 = a2['defects'][0]
                dd_callout += ' In {}, {} leads with {} occurrences.'.format(
                    a2['area'], d2['description'].lower(), d2['count'])

        return render_template('analytics/dashboard.html',
            cycles=cycles, selected_cycle_id='all', selected_cycle=None,
            is_all_view=True, has_data=total_units > 0,
            context_header='Power Park Student Housing - Phase 3 | All Blocks | {} Units'.format(total_units),
            block_comparison=block_comparison,
            summary=summary, area_data=area_data, area_list=area_list, category_data=category_data, category_list=category_list, cat_median=cat_median,
            unit_ranking=unit_ranking, all_units_sorted=all_units_sorted,
            all_areas=all_areas, heatmap=heatmap, area_totals=area_totals,
            unit_totals=unit_totals, recurring=recurring,
            inspector_stats=inspector_stats, area_colours=AREA_COLOURS,
            trend_data=trend_data, area_compare_data=area_compare_data,
            defect_compare=defect_compare, cat_compare_data=cat_compare_data,
            area_deep_dive=area_deep_dive, dd_callout=dd_callout,
            batch_labels=batch_labels, batch_colours=batch_colours,
            pipeline_data=pipeline_data, top_defects=top_defects, td_median=td_median,
            unit_summary=unit_summary, floor_map=floor_map,
            block_floor_grid=block_floor_grid, grid_blocks=grid_blocks,
            grid_floors=grid_floors, grid_median=grid_median,
            floor_labels=FLOOR_LABELS,
            batch_defects_median=batch_defects_median,
            batch_rate_median=batch_rate_median,
            inspector_median=inspector_median)

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
    max_area_count = by_area[0]['cnt'] if by_area else 1
    area_list = []
    for r in by_area:
        area_list.append({
            'area': r['area_name'],
            'count': r['cnt'],
            'pct': round(r['cnt'] / total_defects * 100, 1) if total_defects > 0 else 0,
            'bar_pct': round(r['cnt'] / max_area_count * 100),
            'colour': AREA_COLOURS.get(r['area_name'], '#9ca3af'),
        })

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
    max_cat_count = by_category[0]['cnt'] if by_category else 1
    category_list = []
    for r in by_category:
        category_list.append({
            'category': r['category_name'].upper(),
            'count': r['cnt'],
            'pct': round(r['cnt'] / total_defects * 100, 1) if total_defects > 0 else 0,
            'bar_pct': round(r['cnt'] / max_cat_count * 100),
        })
    cat_counts_sorted = sorted([c['count'] for c in category_list])
    if not cat_counts_sorted:
        cat_median = 0
    elif len(cat_counts_sorted) % 2 == 0:
        cat_median = round((cat_counts_sorted[len(cat_counts_sorted)//2-1] + cat_counts_sorted[len(cat_counts_sorted)//2]) / 2, 1)
    else:
        cat_median = cat_counts_sorted[len(cat_counts_sorted)//2]

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

    # Inspector median for colour coding
    insp_avgs_pc = sorted([r['avg_per_unit'] for r in inspector_stats]) if inspector_stats else []
    if not insp_avgs_pc:
        inspector_median = 0
    elif len(insp_avgs_pc) % 2 == 0:
        inspector_median = round((insp_avgs_pc[len(insp_avgs_pc)//2-1] + insp_avgs_pc[len(insp_avgs_pc)//2]) / 2, 1)
    else:
        inspector_median = insp_avgs_pc[len(insp_avgs_pc)//2]

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

    # Defect rate
    items_inspected = 437 * total_units
    defect_rate = round(total_defects / items_inspected * 100, 1) if items_inspected > 0 else 0
    summary['defect_rate'] = defect_rate
    summary['items_inspected'] = items_inspected

    # Certified count
    certified_count = query_db(
        "SELECT COUNT(*) FROM inspection WHERE cycle_id = ? AND tenant_id = ? AND status = 'certified'",
        [selected_cycle_id, tenant_id], one=True)[0]
    summary['certified_count'] = certified_count

    # Median defects per unit
    counts_list = sorted([r['cnt'] for r in unit_defect_counts]) if unit_defect_counts else []
    if not counts_list:
        median_defects = 0
    elif len(counts_list) % 2 == 0:
        median_defects = round((counts_list[len(counts_list)//2-1] + counts_list[len(counts_list)//2]) / 2, 1)
    else:
        median_defects = counts_list[len(counts_list)//2]
    summary['median_defects'] = median_defects

    floor_map = {0: 'Ground', 1: '1st', 2: '2nd', 3: '3rd'}

    # Pipeline: count inspections by mapped status
    pipeline_raw = query_db("""
        SELECT i.status, COUNT(*) as cnt FROM inspection i
        WHERE i.cycle_id = ? AND i.tenant_id = ?
        GROUP BY i.status
    """, [selected_cycle_id, tenant_id])
    pipe_counts = {r['status']: r['cnt'] for r in pipeline_raw}
    pipeline_total = sum(pipe_counts.values()) or 1
    pipeline_data = [
        {'label': 'Requested', 'count': pipe_counts.get('not_started', 0),
         'pct': round(pipe_counts.get('not_started', 0) / pipeline_total * 100)},
        {'label': 'Inspected', 'count': sum(pipe_counts.get(s, 0) for s in ['in_progress', 'submitted', 'reviewed']),
         'pct': round(sum(pipe_counts.get(s, 0) for s in ['in_progress', 'submitted', 'reviewed']) / pipeline_total * 100)},
        {'label': 'Issued to Site', 'count': sum(pipe_counts.get(s, 0) for s in ['approved', 'certified', 'pending_followup']),
         'pct': round(sum(pipe_counts.get(s, 0) for s in ['approved', 'certified', 'pending_followup']) / pipeline_total * 100)},
    ]

    # Pipeline dates
    pipeline_dates = {}
    cycle_dates = query_db(
        "SELECT request_received_date, created_at FROM inspection_cycle WHERE id = ? AND tenant_id = ?",
        [selected_cycle_id, tenant_id], one=True)
    if cycle_dates:
        pipeline_dates['requested'] = cycle_dates['request_received_date'] or cycle_dates['created_at'][:10] if cycle_dates['created_at'] else ''
    insp_dates_raw = query_db(
        "SELECT MIN(inspection_date) as earliest FROM inspection WHERE cycle_id = ? AND tenant_id = ? AND inspection_date IS NOT NULL",
        [selected_cycle_id, tenant_id], one=True)
    if insp_dates_raw and insp_dates_raw['earliest']:
        pipeline_dates['inspected'] = insp_dates_raw['earliest'][:10]
    approved_dates_raw = query_db(
        "SELECT MAX(approved_at) as latest FROM inspection WHERE cycle_id = ? AND tenant_id = ? AND approved_at IS NOT NULL",
        [selected_cycle_id, tenant_id], one=True)
    if approved_dates_raw and approved_dates_raw['latest']:
        pipeline_dates['issued_to_site'] = approved_dates_raw['latest'][:10]
    for step in pipeline_data:
        key = step['label'].lower().replace(' ', '_')
        step['date'] = pipeline_dates.get(key, '')

    # Top defect types (per-cycle)
    top_defects = query_db("""
        SELECT d.original_comment as description, COUNT(*) as cnt
        FROM defect d
        WHERE d.raised_cycle_id = ? AND d.tenant_id = ? AND d.status = 'open'
        GROUP BY d.original_comment ORDER BY cnt DESC LIMIT 10
    """, [selected_cycle_id, tenant_id])
    td_counts = sorted([r['cnt'] for r in top_defects]) if top_defects else []
    if not td_counts:
        td_median = 0
    elif len(td_counts) % 2 == 0:
        td_median = round((td_counts[len(td_counts)//2-1] + td_counts[len(td_counts)//2]) / 2, 1)
    else:
        td_median = td_counts[len(td_counts)//2]

    # Unit summary with 2-status
    unit_summary_raw = query_db("""
        SELECT u.unit_number, u.block, u.floor, i.status as insp_status,
               COUNT(d.id) as defect_count
        FROM inspection i JOIN unit u ON i.unit_id = u.id
        LEFT JOIN defect d ON d.unit_id = u.id AND d.status = 'open'
            AND d.raised_cycle_id = i.cycle_id
        WHERE i.cycle_id = ? AND i.tenant_id = ?
        GROUP BY u.unit_number, u.block, u.floor, i.status ORDER BY u.unit_number
    """, [selected_cycle_id, tenant_id])
    unit_summary = []
    for r in unit_summary_raw:
        s = r['insp_status']
        display_status = 'Issued to Site' if s in ('approved', 'certified', 'pending_followup') else 'Inspected'
        unit_summary.append({
            'unit_number': r['unit_number'], 'block': r['block'],
            'floor': r['floor'],
            'status': display_status, 'defect_count': r['defect_count'],
            'defect_rate': round(r['defect_count'] / 437 * 100, 1),
        })
    unit_summary.sort(key=lambda x: x['defect_count'], reverse=True)

    # Area Deep Dive: top 3 defect types for top 2 areas (per-cycle)
    deep_dive_raw = query_db("""
        SELECT at2.area_name, d.original_comment, COUNT(*) as cnt
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at2 ON ct.area_id = at2.id
        WHERE d.raised_cycle_id = ? AND d.tenant_id = ? AND d.status = 'open'
        GROUP BY at2.area_name, d.original_comment
        ORDER BY at2.area_name, cnt DESC
    """, [selected_cycle_id, tenant_id])
    dd_map = {}
    dd_area_totals = {}
    for r in deep_dive_raw:
        area = r['area_name']
        desc = r['original_comment']
        if area not in dd_map:
            dd_map[area] = {}
            dd_area_totals[area] = 0
        if desc not in dd_map[area]:
            dd_map[area][desc] = {'total': 0}
        dd_map[area][desc]['total'] += r['cnt']
        dd_area_totals[area] += r['cnt']
    top_areas = sorted(dd_area_totals.keys(), key=lambda a: dd_area_totals[a], reverse=True)[:2]
    dd_colours = ['#C8963E', '#3D6B8E']
    area_deep_dive = []
    for idx, area in enumerate(top_areas):
        descs = dd_map[area]
        top_descs = sorted(descs.items(), key=lambda x: x[1]['total'], reverse=True)[:3]
        max_count = top_descs[0][1]['total'] if top_descs else 1
        defect_list = []
        for desc, info in top_descs:
            defect_list.append({
                'description': desc,
                'count': info['total'],
                'pct': round(info['total'] / dd_area_totals[area] * 100, 1),
                'bar_pct': round(info['total'] / max_count * 100),
            })
        area_deep_dive.append({
            'area': area,
            'total': dd_area_totals[area],
            'pct_of_total': round(dd_area_totals[area] / total_defects * 100, 1) if total_defects > 0 else 0,
            'colour': dd_colours[idx],
            'defects': defect_list,
        })

    # Deep dive callout
    dd_callout = ''
    if len(area_deep_dive) >= 1 and area_deep_dive[0]['defects']:
        a1 = area_deep_dive[0]
        d1 = a1['defects'][0]
        dd_callout = 'The most frequent defect in {} is {} ({} occurrences).'.format(
            a1['area'], d1['description'].lower(), d1['count'])
        if len(area_deep_dive) >= 2 and area_deep_dive[1]['defects']:
            a2 = area_deep_dive[1]
            d2 = a2['defects'][0]
            dd_callout += ' In {}, {} leads with {} occurrences.'.format(
                a2['area'], d2['description'].lower(), d2['count'])

    return render_template('analytics/dashboard.html',
                           cycles=cycles,
                           selected_cycle_id=selected_cycle_id,
                           selected_cycle=selected_cycle,
                           is_all_view=False,
                           context_header=context_header,
                           block_comparison=None,
                           has_data=total_units > 0,
                           summary=summary,
                           area_data=area_data, area_list=area_list,
                           category_data=category_data, category_list=category_list, cat_median=cat_median,
                           unit_ranking=unit_ranking,
                           all_units_sorted=all_units_sorted,
                           all_areas=all_areas,
                           heatmap=heatmap,
                           area_totals=area_totals,
                           unit_totals=unit_totals,
                           recurring=recurring,
                           inspector_stats=inspector_stats,
                           area_colours=AREA_COLOURS,
                           area_deep_dive=area_deep_dive, dd_callout=dd_callout,
                           pipeline_data=pipeline_data, top_defects=top_defects, td_median=td_median,
                           unit_summary=unit_summary, floor_map=floor_map,
                           block_floor_grid={}, grid_blocks=[], grid_floors=[],
                           grid_median=0, floor_labels=FLOOR_LABELS,
                           batch_defects_median=0, batch_rate_median=0,
                           inspector_median=inspector_median)

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
        flash('Not enough data for combined report (need 2+ batches)', 'error')
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
    """Gather data for combined bi-weekly report (all batches/cycles).
    Returns dict with all template variables, or None if fewer than 2 batches.
    All query results converted to plain dicts immediately.
    Supports N batches (not limited to 2).
    """
    import base64, os
    from flask import current_app

    tenant_id = session.get('tenant_id', 'MONOGRAPH')

    def _hex_to_rgba(hex_colour, alpha=0.15):
        """Convert hex colour to rgba string for WeasyPrint compatibility."""
        h = hex_colour.lstrip('#')
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return 'rgba({},{},{},{})'.format(r, g, b, alpha)

    # --- Get all cycles ordered by block, floor ---
    cycles = [dict(r) for r in query_db("""
        SELECT id, cycle_number, block, floor, unit_start, unit_end, status, created_at
        FROM inspection_cycle WHERE tenant_id = ? AND id NOT LIKE 'test-%'
        ORDER BY block, floor
    """, [tenant_id])]

    if len(cycles) < 2:
        return None

    # --- Build batches list (one entry per cycle) ---
    batches = []
    for idx, cyc in enumerate(cycles):
        cid = cyc['id']
        block_name = cyc.get('block') or 'Unknown'
        floor_val = cyc.get('floor', 0)
        floor_label = FLOOR_LABELS.get(floor_val, 'Floor {}'.format(floor_val))
        batch_label = '{} {}'.format(block_name, floor_label)

        # Short label for badges (e.g. "B5G", "B6G", "B5-1F")
        block_num = block_name.replace('Block ', 'B') if 'Block ' in block_name else block_name
        if floor_val == 0:
            short_label = '{}G'.format(block_num)
        else:
            short_label = '{}-{}F'.format(block_num, floor_val)

        colour = BATCH_COLOURS[idx % len(BATCH_COLOURS)]
        colour_bg = _hex_to_rgba(colour, 0.15)

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
            SELECT u.unit_number, u.id as unit_id, u.block, u.floor,
                   COUNT(d.id) as defect_count
            FROM unit u
            JOIN inspection i ON i.unit_id = u.id AND i.cycle_id = ?
            LEFT JOIN defect d ON d.unit_id = u.id AND d.raised_cycle_id = ?
                AND d.status = 'open'
            WHERE u.tenant_id = ?
            GROUP BY u.id ORDER BY u.unit_number
        """, [cid, cid, tenant_id])]

        total_units = len(units)
        total_defects = sum(u['defect_count'] for u in unit_defects)
        avg_defects = round(total_defects / total_units, 1) if total_units > 0 else 0

        # Items per unit
        total_templates = query_db(
            "SELECT COUNT(*) FROM item_template WHERE tenant_id = ?",
            [tenant_id], one=True)[0]
        excluded_count = query_db("""
            SELECT COUNT(DISTINCT ii.item_template_id)
            FROM inspection_item ii JOIN inspection i ON ii.inspection_id = i.id
            WHERE i.cycle_id = ? AND i.tenant_id = ? AND ii.status = 'skipped'
        """, [cid, tenant_id], one=True)[0]
        items_per_unit = total_templates - excluded_count if excluded_count > 0 else 437
        total_items_batch = items_per_unit * total_units
        defect_rate = round((total_defects / total_items_batch) * 100, 1) if total_items_batch > 0 else 0

        insp_dates = [u['inspection_date'] for u in units if u.get('inspection_date')]
        insp_date_display = min(insp_dates)[:10] if insp_dates else None

        # Per-batch worst unit and high defect count
        worst = max(unit_defects, key=lambda x: x['defect_count']) if unit_defects else {'unit_number': '-', 'defect_count': 0}
        high_count = sum(1 for u in unit_defects if u['defect_count'] > 30)

        batches.append({
            'cycle_id': cid,
            'block': block_name,
            'floor': floor_val,
            'label': batch_label,
            'short_label': short_label,
            'colour': colour,
            'colour_bg': colour_bg,
            'total_units': total_units,
            'total_defects': total_defects,
            'avg_defects': avg_defects,
            'items_per_unit': items_per_unit,
            'defect_rate': defect_rate,
            'unit_range': '{}-{}'.format(cyc.get('unit_start', ''), cyc.get('unit_end', '')),
            'inspection_date': insp_date_display,
            'units': units,
            'unit_defects': unit_defects,
            'worst_unit': worst,
            'high_defect_count': high_count,
        })

    # --- Combined totals ---
    total_units = sum(b['total_units'] for b in batches)
    total_defects = sum(b['total_defects'] for b in batches)
    avg_defects = round(total_defects / total_units, 1) if total_units > 0 else 0
    items_per_unit = batches[0]['items_per_unit']
    total_items = items_per_unit * total_units
    defect_rate = round((total_defects / total_items) * 100, 1) if total_items > 0 else 0
    certified_count = sum(
        1 for b in batches
        for u in b['units'] if u.get('unit_status') == 'certified'
    )

    # Combined unit defects (sorted by unit number, tagged with batch info)
    all_unit_defects = []
    for b in batches:
        for ud in b['unit_defects']:
            ud['batch_idx'] = batches.index(b)
            ud['batch_label'] = b['label']
            ud['batch_short'] = b['short_label']
            ud['batch_colour'] = b['colour']
            ud['batch_colour_bg'] = b['colour_bg']
        all_unit_defects.extend(b['unit_defects'])
    all_unit_defects.sort(key=lambda x: x['unit_number'])
    max_defects = max((u['defect_count'] for u in all_unit_defects), default=1)

    # Overall worst unit and high defect stats
    worst_unit = max(all_unit_defects, key=lambda x: x['defect_count']) if all_unit_defects else {'unit_number': '-', 'defect_count': 0}
    high_defect_units = sum(1 for u in all_unit_defects if u['defect_count'] > 30)
    high_defect_pct = round((high_defect_units / total_units) * 100) if total_units > 0 else 0

    # --- Batch index map (cycle_id -> batch index) ---
    batch_idx_map = {b['cycle_id']: i for i, b in enumerate(batches)}

    # --- Area data (combined donut) ---
    area_data_raw = [dict(r) for r in query_db("""
        SELECT at2.area_name as area, COUNT(d.id) as defect_count
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at2 ON ct.area_id = at2.id
        WHERE d.tenant_id = ? AND d.status = 'open'
            AND d.raised_cycle_id NOT LIKE 'test-%%'
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
    for a in area_data_raw:
        mid_frac = (a['offset'] + a['dash'] / 2) / circumference
        angle = mid_frac * 2 * math.pi - math.pi / 2
        a['pct_x'] = round(100 + 70 * math.cos(angle), 1)
        a['pct_y'] = round(100 + 70 * math.sin(angle), 1)

    # --- Area comparison (per-batch via raised_cycle_id) ---
    area_by_batch_raw = [dict(r) for r in query_db("""
        SELECT at2.area_name as area, d.raised_cycle_id as cycle_id, COUNT(*) as cnt
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at2 ON ct.area_id = at2.id
        WHERE d.tenant_id = ? AND d.status = 'open'
            AND d.raised_cycle_id NOT LIKE 'test-%%'
        GROUP BY at2.area_name, d.raised_cycle_id ORDER BY cnt DESC
    """, [tenant_id])]

    area_batch_map = {}
    for r in area_by_batch_raw:
        area_name = r['area']
        if area_name not in area_batch_map:
            area_batch_map[area_name] = [0] * len(batches)
        bidx = batch_idx_map.get(r['cycle_id'])
        if bidx is not None:
            area_batch_map[area_name][bidx] = r['cnt']

    all_area_counts = []
    for counts in area_batch_map.values():
        all_area_counts.extend(counts)
    max_area_count = max(all_area_counts) if all_area_counts else 1

    area_compare = []
    for a in area_data_raw:
        area_name = a['area']
        counts = area_batch_map.get(area_name, [0] * len(batches))
        batch_data = []
        for i, cnt in enumerate(counts):
            batch_data.append({
                'count': cnt,
                'pct': round((cnt / max_area_count) * 100, 1) if max_area_count > 0 else 0,
            })
        area_compare.append({
            'name': area_name,
            'batches': batch_data,
        })

    # --- Trade comparison (per-batch) ---
    trade_by_batch_raw = [dict(r) for r in query_db("""
        SELECT ct.category_name as trade, d.raised_cycle_id as cycle_id, COUNT(*) as cnt
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        WHERE d.tenant_id = ? AND d.status = 'open'
            AND d.raised_cycle_id NOT LIKE 'test-%%'
        GROUP BY ct.category_name, d.raised_cycle_id ORDER BY cnt DESC
    """, [tenant_id])]

    trade_batch_map = {}
    for r in trade_by_batch_raw:
        name = r['trade'].upper()
        if name not in trade_batch_map:
            trade_batch_map[name] = [0] * len(batches)
        bidx = batch_idx_map.get(r['cycle_id'])
        if bidx is not None:
            trade_batch_map[name][bidx] = r['cnt']

    trade_totals = sorted(trade_batch_map.items(),
                          key=lambda x: sum(x[1]), reverse=True)
    max_trade_count = max(
        (v for counts in trade_batch_map.values() for v in counts), default=1)

    trade_compare = []
    for name, counts in trade_totals:
        batch_data = []
        for i, cnt in enumerate(counts):
            batch_data.append({
                'count': cnt,
                'pct': round((cnt / max_trade_count) * 100, 1) if max_trade_count > 0 else 0,
            })
        trade_compare.append({
            'name': name,
            'total': sum(counts),
            'batches': batch_data,
        })

    # --- Top defect types comparison (per-batch) ---
    defect_by_batch_raw = [dict(r) for r in query_db("""
        SELECT d.original_comment as description, d.raised_cycle_id as cycle_id,
               COUNT(*) as cnt
        FROM defect d
        WHERE d.tenant_id = ? AND d.status = 'open'
            AND d.raised_cycle_id NOT LIKE 'test-%%'
        GROUP BY d.original_comment, d.raised_cycle_id ORDER BY cnt DESC
    """, [tenant_id])]

    defect_map = {}
    for r in defect_by_batch_raw:
        desc = r['description']
        if desc not in defect_map:
            defect_map[desc] = {
                'description': desc, 'total': 0,
                'batch_counts': [0] * len(batches),
            }
        defect_map[desc]['total'] += r['cnt']
        bidx = batch_idx_map.get(r['cycle_id'])
        if bidx is not None:
            defect_map[desc]['batch_counts'][bidx] = r['cnt']

    top_defects_compare = sorted(defect_map.values(),
                                 key=lambda x: x['total'], reverse=True)[:15]
    max_defect_total = top_defects_compare[0]['total'] if top_defects_compare else 1
    for d in top_defects_compare:
        d['bar_pct'] = round((d['total'] / max_defect_total) * 100, 1)

    # --- Area deep dive: top 3 defects for top 2 areas, per-batch ---
    combined_area_dive = []
    top_2_areas = [a['area'] for a in area_data_raw[:2]]
    for area_name in top_2_areas:
        top_types = _to_dicts(query_db("""
            SELECT d.original_comment as description, COUNT(*) as total
            FROM defect d
            JOIN item_template it ON d.item_template_id = it.id
            JOIN category_template ct ON it.category_id = ct.id
            JOIN area_template at2 ON ct.area_id = at2.id
            WHERE d.tenant_id = ? AND d.status = 'open' AND at2.area_name = ?
                AND d.raised_cycle_id NOT LIKE 'test-%%'
            GROUP BY d.original_comment ORDER BY total DESC LIMIT 3
        """, [tenant_id, area_name]))

        for dt in top_types:
            dt['batch_counts'] = []
            for batch in batches:
                row = query_db("""
                    SELECT COUNT(*) as cnt FROM defect d
                    JOIN item_template it ON d.item_template_id = it.id
                    JOIN category_template ct ON it.category_id = ct.id
                    JOIN area_template at2 ON ct.area_id = at2.id
                    WHERE d.tenant_id = ? AND d.status = 'open'
                    AND at2.area_name = ? AND d.original_comment = ?
                    AND d.raised_cycle_id = ?
                """, [tenant_id, area_name, dt['description'],
                      batch['cycle_id']], one=True)
                dt['batch_counts'].append(dict(row)['cnt'] if row else 0)

        area_total = next((a['defect_count'] for a in area_data_raw
                           if a['area'] == area_name), 0)
        area_pct = next((a['pct'] for a in area_data_raw
                         if a['area'] == area_name), 0)
        max_count = top_types[0]['total'] if top_types else 1
        for dt in top_types:
            dt['bar_pct'] = round((dt['total'] / max_count) * 100, 1)
        combined_area_dive.append({
            'area': area_name,
            'total': area_total,
            'pct': area_pct,
            'defects': top_types,
        })

    area_colours = ['#C8963E', '#3D6B8E', '#4A7C59', '#C44D3F',
                    '#7B6B8D', '#5A8A7A', '#B07D4B']

    # --- Unit summary table ---
    unit_table = []
    all_unit_map = {}
    for b in batches:
        for u in b['units']:
            all_unit_map[u['unit_number']] = u

    for ud in all_unit_defects:
        info = all_unit_map.get(ud['unit_number'], {})
        variance = round(ud['defect_count'] - avg_defects, 1)
        unit_rate = round((ud['defect_count'] / items_per_unit) * 100, 1) if items_per_unit > 0 else 0
        unit_table.append({
            'unit_number': ud['unit_number'],
            'block': ud.get('block', info.get('block', '')),
            'floor': ud.get('floor', info.get('floor', None)),
            'batch_label': ud.get('batch_label', ''),
            'batch_short': ud.get('batch_short', ''),
            'batch_colour': ud.get('batch_colour', '#6B6B6B'),
            'batch_colour_bg': ud.get('batch_colour_bg', 'rgba(107,107,107,0.15)'),
            'batch_idx': ud.get('batch_idx', 0),
            'inspector_name': info.get('inspector_name', ''),
            'defect_count': ud['defect_count'],
            'defect_rate': unit_rate,
            'variance': variance,
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
        "SELECT id, cycle_number, block, unit_start, unit_end FROM inspection_cycle WHERE tenant_id=? AND id NOT LIKE 'test-%' ORDER BY block, floor",
        [tenant_id], one=False
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

    return {
        'batches': batches,
        'total_units': total_units,
        'total_defects': total_defects,
        'avg_defects': avg_defects,
        'items_per_unit': items_per_unit,
        'defect_rate': defect_rate,
        'certified_count': certified_count,
        'area_data': area_data_raw,
        'area_compare': area_compare,
        'trade_compare': trade_compare,
        'combined_area_dive': combined_area_dive,
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
    items_per_unit = total_templates - excluded_count if excluded_count > 0 else 437

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
        pipeline_dates['issued_to_site'] = max(approved_dates)[:10]

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
        mid_frac = (a['offset'] + a['dash'] / 2) / circumference
        angle = mid_frac * 2 * math.pi - math.pi / 2
        a['pct_x'] = round(100 + 70 * math.cos(angle), 1)
        a['pct_y'] = round(100 + 70 * math.sin(angle), 1)
        offset += a['dash']

    # --- Area deep dive: top 3 defect types for top 2 areas ---
    area_deep_dive = []
    top_area_names = [a['area'] for a in area_data[:2]]
    for area_name in top_area_names:
        area_defects = _to_dicts(query_db("""
            SELECT d.original_comment as description, COUNT(*) as count
            FROM defect d
            JOIN item_template it ON d.item_template_id = it.id
            JOIN category_template ct ON it.category_id = ct.id
            JOIN area_template at2 ON ct.area_id = at2.id
            WHERE d.raised_cycle_id = ? AND d.tenant_id = ? AND d.status = 'open'
            AND at2.area_name = ?
            GROUP BY d.original_comment
            ORDER BY count DESC
            LIMIT 3
        """, [cycle_id, tenant_id, area_name]))
        area_total = next((a['defect_count'] for a in area_data if a['area'] == area_name), 0)
        area_pct = next((a['pct'] for a in area_data if a['area'] == area_name), 0)
        max_count = area_defects[0]['count'] if area_defects else 1
        for d in area_defects:
            d['bar_pct'] = round((d['count'] / max_count) * 100, 1)
            d['item_pct'] = round((d['count'] / area_total) * 100, 1) if area_total > 0 else 0
        area_deep_dive.append({
            'area': area_name,
            'total': area_total,
            'pct': area_pct,
            'defects': area_defects,
        })

        # --- Defects by category (trade) ---
    trade_data = _to_dicts(query_db("""
        SELECT ct.category_name as trade, COUNT(d.id) as defect_count
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        WHERE d.raised_cycle_id = ? AND d.tenant_id = ? AND d.status = 'open'
        GROUP BY ct.category_name
        ORDER BY defect_count DESC
    """, [cycle_id, tenant_id]))

    for td in trade_data:
        td['trade'] = td['trade'].upper()
        td['pct'] = round((td['defect_count'] / total_defects) * 100, 1) if total_defects > 0 else 0

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
        [tenant_id], one=False
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
        'trade_data': trade_data,
        'top_defects': top_defects,
        'unit_table': unit_table,
        'max_defects': max_defects,
        'floor_map': floor_map,
        'cycle_options': cycle_options,
        'logo_b64': logo_b64,
        'sig_b64': sig_b64,
        'area_deep_dive': area_deep_dive,
        'area_colours': report_area_colours,
        'report_date': __import__('datetime').datetime.utcnow().strftime('%d %B %Y'),
    }
