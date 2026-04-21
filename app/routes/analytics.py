"""
Analytics routes - Defect pattern dashboard for managers.
Provides data-driven view of defect patterns across all units in a cycle.
Access: Manager + Admin only.
"""
from flask import Blueprint, render_template, session, request, make_response
from app.auth import require_manager, require_office_admin, require_team_lead
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



# ============================================================
# ANALYTICS DASHBOARD v2 - Block+Floor Cards
# ============================================================

ITEMS_PER_UNIT = 437
PROJECT_TOTAL_UNITS = 191
CARD_COLOURS = ['#C8963E', '#3D6B8E', '#4A7C59', '#C44D3F', '#7B6B8D', '#5A8A7A', '#B07D4B']


def _block_to_slug(block_name):
    """Convert block name to URL slug: 'Block 5' -> 'block-5'."""
    return block_name.lower().replace(' ', '-')


def _slug_to_block(slug):
    """Convert URL slug back to block name: 'block-5' -> 'Block 5'."""
    return slug.replace('-', ' ').title()


@analytics_bp.route('/')
@require_manager
def dashboard():
    """Analytics Dashboard - block+floor cards with project overview."""
    tenant_id = session.get('tenant_id', 'MONOGRAPH')

    # 1. Unit counts per block+floor
    unit_counts_raw = query_db("""
        SELECT u.block, u.floor, COUNT(DISTINCT u.id) as total_units
        FROM unit_real u
        WHERE u.tenant_id = ? AND u.unit_number NOT LIKE 'TEST%'
        GROUP BY u.block, u.floor
        ORDER BY u.block, u.floor
    """, [tenant_id])
    unit_counts = [dict(r) for r in unit_counts_raw]

    if not unit_counts:
        return render_template('analytics/dashboard_v2.html',
                               has_data=False, cards=[], project={})

    # 2. Open defects per block+floor
    defect_counts_raw = query_db("""
        SELECT u.block, u.floor, COUNT(d.id) as open_defects
        FROM defect d
        JOIN unit_real u ON d.unit_id = u.id
        WHERE d.tenant_id = ? AND d.status = 'open'
        AND d.raised_cycle_id NOT LIKE 'test-%'
        AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
        AND d.raised_cycle_number = 1
        GROUP BY u.block, u.floor
    """, [tenant_id])
    defect_map = {}
    for r in defect_counts_raw:
        defect_map[(r['block'], r['floor'])] = r['open_defects']

    # 3. Round breakdown per block+floor
    rounds_raw = query_db("""
        SELECT u.block, u.floor, i.cycle_number as round_number,
            COUNT(DISTINCT i.unit_id) as units_inspected
        FROM inspection i
        JOIN unit_real u ON i.unit_id = u.id
        WHERE i.tenant_id = ? AND i.cycle_id NOT LIKE 'test-%'
        AND i.status IN ('reviewed','approved','certified','pending_followup')
        GROUP BY u.block, u.floor, i.cycle_number
        ORDER BY u.block, u.floor, i.cycle_number
    """, [tenant_id])
    rounds_map = {}
    for r in rounds_raw:
        key = (r['block'], r['floor'])
        if key not in rounds_map:
            rounds_map[key] = []
        rounds_map[key].append({
            'round_number': r['round_number'],
            'units_inspected': r['units_inspected'],
        })

    # 4. Certified counts per block+floor
    certified_raw = query_db("""
        SELECT u.block, u.floor, COUNT(DISTINCT i.unit_id) as certified
        FROM inspection i
        JOIN unit_real u ON i.unit_id = u.id
        WHERE i.tenant_id = ? AND i.status = 'certified'
        AND i.cycle_id NOT LIKE 'test-%'
        GROUP BY u.block, u.floor
    """, [tenant_id])
    certified_map = {}
    for r in certified_raw:
        certified_map[(r['block'], r['floor'])] = r['certified']

    # 4b. Inspected units per block+floor
    inspected_zone_raw = query_db("""
        SELECT u.block, u.floor, COUNT(DISTINCT i.unit_id) as inspected
        FROM inspection i
        JOIN unit_real u ON i.unit_id = u.id
        WHERE i.tenant_id = ? AND i.cycle_id NOT LIKE 'test-%'
        AND i.status IN ('reviewed','approved','certified','pending_followup')
        AND i.cycle_number = 1
        GROUP BY u.block, u.floor
    """, [tenant_id])
    inspected_zone_map = {}
    for r in inspected_zone_raw:
        inspected_zone_map[(r['block'], r['floor'])] = r['inspected']

    # 5. Build cards
    cards = []
    total_units_project = 0
    total_defects_project = 0
    total_certified_project = 0

    for idx, uc in enumerate(unit_counts):
        key = (uc['block'], uc['floor'])
        total_units = uc['total_units']
        open_defects = defect_map.get(key, 0)
        rounds = rounds_map.get(key, [])
        certified = certified_map.get(key, 0)
        inspected = inspected_zone_map.get(key, 0)
        max_round = max((r['round_number'] for r in rounds), default=0)
        avg_defects = round(open_defects / inspected, 1) if inspected > 0 else 0
        items_inspected = ITEMS_PER_UNIT * inspected
        defect_rate = round(open_defects / items_inspected * 100, 1) if items_inspected > 0 else 0

        floor_label = FLOOR_LABELS.get(uc['floor'], 'Floor {}'.format(uc['floor']))

        cards.append({
            'block': uc['block'],
            'floor': uc['floor'],
            'floor_label': floor_label,
            'label': '{} {}'.format(uc['block'], floor_label),
            'block_slug': _block_to_slug(uc['block']),
            'total_units': total_units,
            'inspected': inspected,
            'open_defects': open_defects,
            'avg_defects': avg_defects,
            'defect_rate': defect_rate,
            'rounds': rounds,
            'max_round': max_round,
            'certified': certified,
            'colour': CARD_COLOURS[idx % len(CARD_COLOURS)],
        })

        total_units_project += total_units
        total_defects_project += open_defects
        total_certified_project += certified

    # 6. Project overview
    items_project = ITEMS_PER_UNIT * total_units_project
    project = {
        'total_units': total_units_project,
        'open_defects': total_defects_project,
        'avg_defects': round(total_defects_project / total_units_project, 1) if total_units_project > 0 else 0,
        'defect_rate': round(total_defects_project / items_project * 100, 1) if items_project > 0 else 0,
        'certified': total_certified_project,
    }

    # 7. Inspected-only metrics (honest numbers)
    inspected_raw = query_db("""
        SELECT COUNT(DISTINCT i.unit_id) as inspected
        FROM inspection i
        JOIN unit_real u ON u.id = i.unit_id
        WHERE i.tenant_id = ? AND i.cycle_id NOT LIKE 'test-%'
        AND i.status IN ('reviewed','approved','certified','pending_followup')
        AND i.cycle_number = 1
    """, [tenant_id], one=True)
    units_inspected = inspected_raw['inspected'] if inspected_raw else 0
    items_inspected = ITEMS_PER_UNIT * units_inspected
    project['units_inspected'] = units_inspected
    project['pct_complete'] = round(units_inspected / PROJECT_TOTAL_UNITS * 100) if PROJECT_TOTAL_UNITS > 0 else 0
    project['avg_defects_inspected'] = round(total_defects_project / units_inspected, 1) if units_inspected > 0 else 0
    project['defect_rate_inspected'] = round(total_defects_project / items_inspected * 100, 1) if items_inspected > 0 else 0
    project['items_inspected'] = items_inspected
    project['project_total'] = PROJECT_TOTAL_UNITS

    # 7c. Completion forecast
    from datetime import date, timedelta
    forecast_raw = query_db("""
        SELECT MIN(inspection_date) as first_date,
               MAX(inspection_date) as last_date,
               COUNT(DISTINCT i.unit_id) as done
        FROM inspection i
        JOIN unit_real u ON u.id = i.unit_id
        WHERE i.tenant_id = ? AND i.cycle_id NOT LIKE 'test-%'
        AND i.status IN ('submitted','reviewed','approved','pending_followup','certified')
        AND i.inspection_date IS NOT NULL
        AND u.unit_number NOT LIKE 'TEST%'
        AND i.cycle_number = 1
    """, [tenant_id], one=True)
    forecast = None
    if forecast_raw and forecast_raw['first_date'] and forecast_raw['last_date'] and forecast_raw['done']:
        first = date.fromisoformat(forecast_raw['first_date'])
        last = date.fromisoformat(forecast_raw['last_date'])
        done = forecast_raw['done']
        elapsed = (last - first).days or 1
        rate = done / elapsed
        remaining = PROJECT_TOTAL_UNITS - done
        days_left = round(remaining / rate) if rate > 0 else None
        est_date = last + timedelta(days=days_left) if days_left else None
        forecast = {
            'est_date': est_date.strftime('%-d %b %Y') if est_date else 'N/A',
            'rate': round(rate, 1),
            'rate_week': round(rate * 7, 1),
            'remaining': remaining,
            'done': done,
        }
    project['forecast'] = forecast

    # Set heatmap benchmark to project average
    grid_median = project['avg_defects_inspected']

    # 7b. Median, min, max defects per unit (inspected only)
    unit_defect_counts_raw = query_db("""
        SELECT COUNT(d.id) as defect_count
        FROM inspection i
        JOIN unit_real u ON i.unit_id = u.id
        LEFT JOIN defect d ON d.unit_id = u.id AND d.status = 'open'
            AND d.raised_cycle_id NOT LIKE 'test-%' AND d.tenant_id = u.tenant_id
            AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
            AND d.raised_cycle_number = 1
        WHERE i.tenant_id = ? AND i.cycle_id NOT LIKE 'test-%'
        AND i.status IN ('reviewed','approved','certified','pending_followup')
        AND i.cycle_number = 1
        AND u.unit_number NOT LIKE 'TEST%'
        GROUP BY u.id
        ORDER BY defect_count
    """, [tenant_id])
    unit_counts_list = [r['defect_count'] for r in unit_defect_counts_raw]
    if unit_counts_list:
        n = len(unit_counts_list)
        if n % 2 == 0:
            median_val = (unit_counts_list[n // 2 - 1] + unit_counts_list[n // 2]) / 2
        else:
            median_val = unit_counts_list[n // 2]
        project['median_defects'] = round(median_val, 1)
        project['min_defects'] = unit_counts_list[0]
        project['max_defects'] = unit_counts_list[-1]
    else:
        project['median_defects'] = 0
        project['min_defects'] = 0
        project['max_defects'] = 0

    # Q1/Q3 for unit-level traffic lights
    def _quartile(data, q):
        if not data:
            return 0
        idx = (len(data) - 1) * q / 100
        lo, hi = int(idx), min(int(idx) + 1, len(data) - 1)
        return data[lo] + (data[hi] - data[lo]) * (idx - lo)

    q1 = round(_quartile(unit_counts_list, 25), 1) if unit_counts_list else 0
    q3 = round(_quartile(unit_counts_list, 75), 1) if unit_counts_list else 0

    # 8. Rectification pulse (R2+ data)
    rect_raw = query_db("""
        SELECT
            COUNT(*) as total_reviewed
        FROM defect d
        WHERE d.tenant_id = ? AND d.raised_cycle_id NOT LIKE 'test-%'
        AND d.status = 'cleared'
    """, [tenant_id], one=True)

    r2_units_raw = query_db("""
        SELECT COUNT(DISTINCT i.unit_id) as r2_units
        FROM inspection i
        WHERE i.tenant_id = ? AND i.cycle_number > 1
        AND i.cycle_id NOT LIKE 'test-%' AND i.status IN ('reviewed','approved','certified','pending_followup')
    """, [tenant_id], one=True)

    r2_new_raw = query_db("""
        SELECT COUNT(*) as new_defects
        FROM defect d
        WHERE d.tenant_id = ? AND d.raised_cycle_number > 1
        AND d.raised_cycle_id NOT LIKE 'test-%' AND d.status = 'open'
    """, [tenant_id], one=True)

    rectification = None
    r2_units = r2_units_raw['r2_units'] if r2_units_raw else 0
    if r2_units > 0:
        total_cleared = rect_raw['total_reviewed'] or 0 if rect_raw else 0
        r2_new = r2_new_raw['new_defects'] or 0 if r2_new_raw else 0
        # Clearance % = cleared / (cleared + still_open_from_prior)
        # For now use cleared / total_reviewed as proxy
        clearance_pct = 100.0 if total_cleared > 0 else 0
        net_imp = total_cleared - r2_new
        rectification = {
            'r2_units': r2_units,
            'total_reviewed': total_cleared,
            'rectified': total_cleared,
            'superseded': 0,
            'new_defects': r2_new,
            'clearance_pct': clearance_pct,
            'net_improvement': net_imp,
        }

    # 9. Area breakdown (top problem areas)
    area_data = [dict(r) for r in query_db("""
        SELECT at2.area_name AS area, COUNT(d.id) AS defect_count
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at2 ON ct.area_id = at2.id
        WHERE d.tenant_id = ? AND d.status = 'open'
        AND d.raised_cycle_id NOT LIKE 'test-%'
        AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
        AND d.raised_cycle_number = 1
        GROUP BY at2.area_name
        ORDER BY defect_count DESC
    """, [tenant_id])]
    area_max = area_data[0]['defect_count'] if area_data else 1

    # Area median for colour coding
    area_counts_sorted = sorted([a['defect_count'] for a in area_data])
    if area_counts_sorted:
        mid = len(area_counts_sorted) // 2
        area_median = area_counts_sorted[mid] if len(area_counts_sorted) % 2 else (area_counts_sorted[mid - 1] + area_counts_sorted[mid]) / 2
    else:
        area_median = 0
    # Top 2 areas insight
    area_top2_sum = sum(a['defect_count'] for a in area_data[:2]) if len(area_data) >= 2 else 0
    area_top2_pct = round(area_top2_sum / project['open_defects'] * 100) if project['open_defects'] > 0 else 0
    area_top2_names = [a['area'].title() for a in area_data[:2]] if len(area_data) >= 2 else []

    # Area Deep Dive - top 3 defects in top 2 areas (project-wide)
    area_deep_dive = []
    dd_colours = ['#C8963E', '#3D6B8E']
    for idx, area_row in enumerate(area_data[:2]):
        area_name = area_row['area']
        area_defects = [dict(r) for r in query_db("""
            SELECT d.original_comment AS description, COUNT(*) AS count
            FROM defect d
            JOIN item_template it ON d.item_template_id = it.id
            JOIN category_template ct ON it.category_id = ct.id
            JOIN area_template at2 ON ct.area_id = at2.id
            WHERE d.tenant_id = ? AND d.status = 'open'
            AND d.raised_cycle_id NOT LIKE 'test-%'
            AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
            AND d.raised_cycle_number = 1
            AND at2.area_name = ?
            GROUP BY d.original_comment
            ORDER BY count DESC
            LIMIT 3
        """, [tenant_id, area_name])]
        max_dd = area_defects[0]['count'] if area_defects else 1
        for d in area_defects:
            d['bar_pct'] = round(d['count'] / max_dd * 100)
        area_pct = round(area_row['defect_count'] / project['open_defects'] * 100, 1) if project['open_defects'] > 0 else 0
        area_deep_dive.append({
            'area': area_name,
            'total': area_row['defect_count'],
            'pct': area_pct,
            'colour': dd_colours[idx],
            'defects': area_defects,
        })

    dd_callout = ''
    if len(area_deep_dive) >= 1 and area_deep_dive[0]['defects']:
        a1 = area_deep_dive[0]
        d1 = a1['defects'][0]
        dd_callout = 'The most frequent defect in {} is {} ({} occurrences).'.format(
            a1['area'].title(), d1['description'].lower(), d1['count'])
        if len(area_deep_dive) >= 2 and area_deep_dive[1]['defects']:
            a2 = area_deep_dive[1]
            d2 = a2['defects'][0]
            dd_callout += ' In {}, {} leads with {} occurrences.'.format(
                a2['area'].title(), d2['description'].lower(), d2['count'])


    # 10. Worst units (top 5)
    worst_units = [dict(r) for r in query_db("""
        SELECT u.id as unit_id, u.unit_number, u.block, u.floor,
               COUNT(d.id) as defect_count
        FROM defect d
        JOIN unit_real u ON d.unit_id = u.id
        WHERE d.tenant_id = ? AND d.status = 'open'
        AND d.raised_cycle_id NOT LIKE 'test-%'
        AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
        AND d.raised_cycle_number = 1
        GROUP BY u.id, u.unit_number, u.block, u.floor
        ORDER BY defect_count DESC
        LIMIT 5
    """, [tenant_id])]

    # Worst units insight for footer
    worst_sum = sum(u['defect_count'] for u in worst_units)
    worst_pct = round(worst_sum / project['open_defects'] * 100) if project['open_defects'] > 0 else 0
    worst_blocks = {}
    for u in worst_units:
        key = u['block'] + ' ' + FLOOR_LABELS.get(u['floor'], 'Floor ' + str(u['floor']))
        worst_blocks[key] = worst_blocks.get(key, 0) + 1
    worst_dominant = max(worst_blocks.items(), key=lambda x: x[1]) if worst_blocks else ('', 0)

    # 11. Top 10 defect types (project-wide)
    top_defects_raw = query_db("""
        SELECT original_comment AS description, COUNT(*) AS cnt
        FROM defect
        WHERE tenant_id = ? AND status = 'open'
        AND raised_cycle_id NOT LIKE 'test-%'
        AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = defect.unit_id AND i2.cycle_id = defect.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
        AND defect.raised_cycle_number = 1
        GROUP BY original_comment
        ORDER BY cnt DESC
        LIMIT 10
    """, [tenant_id])
    top_defects = [dict(r) for r in top_defects_raw]
    td_counts = sorted([d['cnt'] for d in top_defects])
    if td_counts:
        mid = len(td_counts) // 2
        td_median = td_counts[mid] if len(td_counts) % 2 else (td_counts[mid - 1] + td_counts[mid]) / 2
    else:
        td_median = 0

    # 12. Defects by category/trade (project-wide)
    category_raw = query_db("""
        SELECT ct.category_name AS category, COUNT(d.id) AS count
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        WHERE d.tenant_id = ? AND d.status = 'open'
        AND d.raised_cycle_id NOT LIKE 'test-%'
        AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
        AND d.raised_cycle_number = 1
        GROUP BY ct.category_name
        ORDER BY count DESC
    """, [tenant_id])
    category_data = [dict(r) for r in category_raw]
    cat_counts = sorted([c['count'] for c in category_data])
    if cat_counts:
        mid = len(cat_counts) // 2
        cat_median = cat_counts[mid] if len(cat_counts) % 2 else (cat_counts[mid - 1] + cat_counts[mid]) / 2
    else:
        cat_median = 0

    # 13. Systemic/recurring defects (3+ units)
    recurring_raw = query_db("""
        SELECT d.original_comment,
            COUNT(d.id) AS cnt,
            COUNT(DISTINCT d.unit_id) AS unit_count,
            GROUP_CONCAT(DISTINCT u.unit_number) AS affected_units
        FROM defect d
        JOIN unit_real u ON d.unit_id = u.id
        WHERE d.tenant_id = ? AND d.status = 'open'
        AND d.raised_cycle_id NOT LIKE 'test-%'
        AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
        AND d.raised_cycle_number = 1
        GROUP BY d.original_comment
        HAVING unit_count >= 3
        ORDER BY cnt DESC
        LIMIT 10
    """, [tenant_id])
    recurring = [dict(r) for r in recurring_raw]
    # Category breakdown for top 10 descriptions
    if recurring:
        top_comments = [r['original_comment'] for r in recurring]
        placeholders = ','.join('?' * len(top_comments))
        cat_raw = query_db("""
            SELECT d.original_comment, ct.category_name, COUNT(d.id) AS cat_cnt
            FROM defect d
            JOIN item_template it ON d.item_template_id = it.id
            JOIN category_template ct ON it.category_id = ct.id
            WHERE d.tenant_id = ? AND d.status = 'open'
            AND d.raised_cycle_id NOT LIKE 'test-%'
            AND d.original_comment IN ({})
            AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
            AND d.raised_cycle_number = 1
            GROUP BY d.original_comment, ct.category_name
            ORDER BY d.original_comment, cat_cnt DESC
        """.format(placeholders), [tenant_id] + top_comments)
        from collections import defaultdict
        cat_map = defaultdict(list)
        for row in cat_raw:
            cat_map[row['original_comment']].append({'cat': row['category_name'], 'cnt': row['cat_cnt']})
        for r in recurring:
            r['cat_breakdown'] = cat_map.get(r['original_comment'], [])

    # 14. Build density grid from cards
    grid_blocks = sorted(set(c['block'] for c in cards if c['inspected'] > 0))
    grid_floors = sorted(set(c['floor'] for c in cards if c['inspected'] > 0))
    block_floor_grid = {}
    grid_avgs = []
    for c in cards:
        if c['inspected'] > 0:
            if c['block'] not in block_floor_grid:
                block_floor_grid[c['block']] = {}
            block_floor_grid[c['block']][c['floor']] = {
                'avg': c['avg_defects'],
                'defects': c['open_defects'],
                'units': c['inspected'],
                'defect_rate': c['defect_rate'],
            }
            grid_avgs.append(c['avg_defects'])
    # grid_median is set earlier (line ~204) to project avg_defects_inspected


    # 15. Inspector analytics (zone-adjusted scores)
    inspector_raw = [dict(r) for r in query_db("""
        SELECT i.inspector_name,
            u.unit_number, u.block, u.floor,
            COUNT(d.id) as defect_count
        FROM inspection i
        JOIN unit_real u ON i.unit_id = u.id
        LEFT JOIN defect d ON d.unit_id = u.id AND d.raised_cycle_id = i.cycle_id
            AND d.status = 'open' AND d.tenant_id = u.tenant_id
        WHERE i.tenant_id = ? AND i.cycle_number = 1 AND i.status IN ('reviewed','approved','certified','pending_followup')
            AND i.inspector_name IS NOT NULL
            AND u.unit_number NOT LIKE 'TEST%'
        GROUP BY i.inspector_name, u.unit_number, u.block, u.floor
        ORDER BY i.inspector_name
    """, [tenant_id])]

    # Build zone averages from cards
    zone_avgs = {}
    for c in cards:
        if c['inspected'] > 0:
            zone_avgs[(c['block'], c['floor'])] = c['avg_defects']

    # Calculate per-inspector zone-adjusted scores
    from collections import defaultdict
    insp_data = defaultdict(lambda: {'units': 0, 'total_defects': 0, 'variances': [], 'areas': defaultdict(int), 'unit_list': []})
    for r in inspector_raw:
        name = r['inspector_name']
        zone_key = (r['block'], r['floor'])
        zone_avg = zone_avgs.get(zone_key, 0)
        variance_pct = round((r['defect_count'] - zone_avg) / zone_avg * 100, 1) if zone_avg > 0 else 0
        insp_data[name]['units'] += 1
        insp_data[name]['total_defects'] += r['defect_count']
        insp_data[name]['variances'].append(variance_pct)
        insp_data[name]['unit_list'].append({
            'unit': r['unit_number'], 'block': r['block'], 'floor': r['floor'],
            'defects': r['defect_count'], 'zone_avg': zone_avg, 'variance': variance_pct
        })

    import statistics
    inspector_cards = []
    for name, d in insp_data.items():
        avg_variance = round(sum(d['variances']) / len(d['variances']), 1) if d['variances'] else 0
        consistency = round(statistics.stdev(d['variances']), 1) if len(d['variances']) > 1 else 0
        raw_avg = round(d['total_defects'] / d['units'], 1) if d['units'] > 0 else 0
        inspector_cards.append({
            'name': name,
            'units': d['units'],
            'total_defects': d['total_defects'],
            'raw_avg': raw_avg,
            'zone_score': avg_variance,
            'consistency': consistency,
            'colour': '#C44D3F' if abs(avg_variance) > 30 else '#C8963E' if abs(avg_variance) > 15 else '#4A7C59',
        })
    inspector_cards.sort(key=lambda x: x['zone_score'], reverse=True)

    # Separate active vs awaiting blocks (a block is active if ANY zone has inspections)
    active_blocks = set()
    for card in cards:
        if card['inspected'] > 0:
            active_blocks.add(card['block'])

    # Batch list for view selector
    all_batches_raw = query_db("""
        SELECT id, name, status FROM inspection_batch
        WHERE tenant_id = ? AND status IN ('reviewed', 'complete')
        ORDER BY created_at DESC
    """, [tenant_id])
    all_batches = [dict(r) for r in all_batches_raw]

    return render_template('analytics/dashboard_v2.html',
                           has_data=True,
                           cards=cards,
                           project=project,
                           rectification=rectification,
                           area_data=area_data,
                           area_max=area_max,
                           area_colours=AREA_COLOURS,
                           area_median=area_median,
                           area_top2_pct=area_top2_pct,
                           area_top2_names=area_top2_names,
                           area_deep_dive=area_deep_dive,
                           dd_callout=dd_callout,
                           worst_pct=worst_pct,
                           worst_dominant_zone=worst_dominant[0],
                           worst_dominant_count=worst_dominant[1],
                           worst_units=worst_units,
                           active_blocks=active_blocks,
                           floor_labels=FLOOR_LABELS,
                           top_defects=top_defects,
                           td_median=td_median,
                           category_data=category_data,
                           cat_median=cat_median,
                           recurring=recurring,
                           grid_blocks=grid_blocks,
                           grid_floors=grid_floors,
                           block_floor_grid=block_floor_grid,
                           q1=q1,
                           q3=q3,
                           grid_median=grid_median,
                           inspector_cards=inspector_cards,
                           all_batches=all_batches,
                           forecast=project.get('forecast'))


@analytics_bp.route('/batch/<batch_id>')
@require_manager
def batch_analytics(batch_id):
    """Batch-level analytics dashboard."""
    tenant_id = session.get('tenant_id', 'MONOGRAPH')

    # 1. Batch metadata
    batch_row = query_db("""
        SELECT ib.id, ib.name, ib.status, ib.created_at,
               COUNT(DISTINCT bu.id) as total_units
        FROM inspection_batch ib
        LEFT JOIN batch_unit bu ON bu.batch_id = ib.id AND bu.removed_at IS NULL
        WHERE ib.id = ? AND ib.tenant_id = ?
        GROUP BY ib.id
    """, [batch_id, tenant_id], one=True)
    if not batch_row:
        return "Batch not found", 404
    batch = dict(batch_row)

    # 2. Project average benchmark
    proj_avg_row = query_db("""
        SELECT AVG(sub.defect_count) as project_avg
        FROM (
            SELECT i.unit_id, COUNT(d.id) as defect_count
            FROM inspection i
            JOIN unit_real u ON i.unit_id = u.id
            LEFT JOIN defect d ON d.unit_id = i.unit_id
                AND d.raised_cycle_id = i.cycle_id
                AND d.status = 'open'
                AND d.tenant_id = i.tenant_id
            WHERE i.tenant_id = ?
            AND i.status IN ('reviewed','approved','certified','pending_followup')
            AND u.unit_number NOT LIKE 'TEST%'
            AND i.cycle_id NOT LIKE 'test-%'
            GROUP BY i.unit_id
        ) sub
    """, [tenant_id], one=True)
    project_avg_raw = proj_avg_row['project_avg'] or 0 if proj_avg_row and proj_avg_row['project_avg'] else 0
    project_avg = round(project_avg_raw, 1)

    # 3. Zones in this batch
    zones_raw = [dict(r) for r in query_db("""
        SELECT ic.block, ic.floor, ic.id as cycle_id, ic.cycle_number,
               COUNT(DISTINCT bu.unit_id) as zone_units
        FROM batch_unit bu
        JOIN inspection_cycle ic ON bu.cycle_id = ic.id
        WHERE bu.batch_id = ? AND bu.removed_at IS NULL AND bu.tenant_id = ?
        GROUP BY ic.block, ic.floor, ic.id, ic.cycle_number
        ORDER BY ic.block, ic.floor
    """, [batch_id, tenant_id])]
    all_cycle_ids = [z['cycle_id'] for z in zones_raw]

    # 4. Build zone data
    zones = []
    batch_total_defects = 0
    batch_total_inspected = 0
    reviewed_statuses = ('reviewed', 'approved', 'certified', 'pending_followup')

    for z in zones_raw:
        cycle_id = z['cycle_id']
        block = z['block']
        floor = z['floor']
        cycle_number = z['cycle_number']

        unit_rows = [dict(r) for r in query_db("""
            SELECT u.unit_number, u.id as unit_id,
                   COUNT(d.id) as defect_count,
                   i.status as insp_status
            FROM batch_unit bu
            JOIN unit_real u ON bu.unit_id = u.id
            LEFT JOIN defect d ON d.unit_id = u.id
                AND d.raised_cycle_id = ?
                AND d.status = 'open'
                AND d.tenant_id = u.tenant_id
            LEFT JOIN inspection i ON i.unit_id = u.id AND i.cycle_id = ?
            WHERE bu.batch_id = ? AND bu.removed_at IS NULL
            AND bu.cycle_id = ? AND bu.tenant_id = ?
            GROUP BY u.id, u.unit_number, i.status
            ORDER BY u.unit_number
        """, [cycle_id, cycle_id, batch_id, cycle_id, tenant_id])]

        inspected_units = [u for u in unit_rows if u['insp_status'] in reviewed_statuses]
        zone_inspected = len(inspected_units)
        zone_defects = sum(u['defect_count'] for u in inspected_units)
        zone_avg = round(zone_defects / zone_inspected, 1) if zone_inspected > 0 else 0

        # Rectification context (R2+)
        rectification = None
        if cycle_number > 1 and inspected_units:
            prev_cycle_row = query_db("""
                SELECT id FROM inspection_cycle
                WHERE block = ? AND floor = ? AND cycle_number = ? AND tenant_id = ?
            """, [block, floor, cycle_number - 1, tenant_id], one=True)
            if prev_cycle_row:
                prev_cycle_id = prev_cycle_row['id']
                unit_ids = [u['unit_id'] for u in inspected_units]
                ph = ','.join('?' * len(unit_ids))
                r1_row = query_db(
                    'SELECT COUNT(*) as cnt FROM defect WHERE raised_cycle_id = ? AND unit_id IN (' + ph + ') AND tenant_id = ?',
                    [prev_cycle_id] + unit_ids + [tenant_id], one=True)
                cleared_row = query_db(
                    'SELECT COUNT(*) as cnt FROM defect WHERE cleared_cycle_id = ? AND unit_id IN (' + ph + ') AND tenant_id = ?',
                    [cycle_id] + unit_ids + [tenant_id], one=True)
                new_row = query_db(
                    'SELECT COUNT(*) as cnt FROM defect WHERE raised_cycle_id = ? AND unit_id IN (' + ph + ') AND tenant_id = ?',
                    [cycle_id] + unit_ids + [tenant_id], one=True)
                r1_count = r1_row['cnt'] if r1_row else 0
                cleared_count = cleared_row['cnt'] if cleared_row else 0
                new_count = new_row['cnt'] if new_row else 0
                still_open = max(r1_count - cleared_count, 0)
                clearance_pct = round(cleared_count / r1_count * 100) if r1_count > 0 else 0
                rectification = {
                    'r1_raised': r1_count, 'cleared': cleared_count,
                    'new': new_count, 'still_open': still_open,
                    'clearance_pct': clearance_pct,
                }

        # Traffic light assigned after quartiles calculated (placeholder)
        zone_traffic = 'green'
        zone_delta = 0

        floor_label = FLOOR_LABELS.get(floor, 'Floor {}'.format(floor))
        zones.append({
            'block': block, 'floor': floor, 'floor_label': floor_label,
            'label': '{} {}'.format(block, floor_label),
            'cycle_id': cycle_id, 'cycle_number': cycle_number,
            'total_units': z['zone_units'], 'inspected': zone_inspected,
            'defects': zone_defects, 'avg': zone_avg,
            'traffic': zone_traffic, 'delta': zone_delta,
            'units': unit_rows, 'rectification': rectification,
            'block_slug': _block_to_slug(block),
        })
        batch_total_defects += zone_defects
        batch_total_inspected += zone_inspected

    # 5. Batch KPIs
    batch_avg = round(batch_total_defects / batch_total_inspected, 1) if batch_total_inspected > 0 else 0
    batch_items = ITEMS_PER_UNIT * batch_total_inspected
    batch_defect_rate = round(batch_total_defects / batch_items * 100, 1) if batch_items > 0 else 0
    proj_defect_rate = round(project_avg_raw / ITEMS_PER_UNIT * 100, 1) if project_avg_raw > 0 else 0

    # Quartile banding across all inspected units in batch
    all_unit_counts = []
    for z in zones:
        for u in z['units']:
            if u['insp_status'] in reviewed_statuses:
                all_unit_counts.append(u['defect_count'])
    if len(all_unit_counts) >= 4:
        all_unit_counts_sorted = sorted(all_unit_counts)
        n_units = len(all_unit_counts_sorted)
        q1 = all_unit_counts_sorted[n_units // 4]
        q3 = all_unit_counts_sorted[(n_units * 3) // 4]
    elif all_unit_counts:
        q1 = min(all_unit_counts)
        q3 = max(all_unit_counts)
    else:
        q1 = q3 = 0

    # Apply quartile traffic to zones
    for z in zones:
        if z['inspected'] > 0 and q3 > 0:
            if z['avg'] <= q1:
                z['traffic'] = 'green'
            elif z['avg'] <= q3:
                z['traffic'] = 'amber'
            else:
                z['traffic'] = 'red'
        else:
            z['traffic'] = 'green'

    # Apply quartile traffic to individual units
    for z in zones:
        for u in z['units']:
            if u['insp_status'] in reviewed_statuses and q3 > 0:
                if u['defect_count'] <= q1:
                    u['traffic'] = 'green'
                elif u['defect_count'] <= q3:
                    u['traffic'] = 'amber'
                else:
                    u['traffic'] = 'red'
            else:
                u['traffic'] = 'grey'

    # Batch-level traffic
    if batch_avg > 0 and q3 > 0:
        if batch_avg <= q1:
            batch_traffic = 'green'
        elif batch_avg <= q3:
            batch_traffic = 'amber'
        else:
            batch_traffic = 'red'
    else:
        batch_traffic = 'green'
    delta_val = 0
    delta_label = 'Q1: {} | Q3: {}'.format(q1, q3)

    all_unit_counts_sorted2 = sorted(all_unit_counts) if all_unit_counts else []
    if all_unit_counts_sorted2:
        n2 = len(all_unit_counts_sorted2)
        batch_median = all_unit_counts_sorted2[n2 // 2] if n2 % 2 else (all_unit_counts_sorted2[n2 // 2 - 1] + all_unit_counts_sorted2[n2 // 2]) / 2
        batch_min = all_unit_counts_sorted2[0]
        batch_max = all_unit_counts_sorted2[-1]
    else:
        batch_median = batch_min = batch_max = 0

    kpis = {
        'total_units': batch['total_units'], 'inspected': batch_total_inspected,
        'total_defects': batch_total_defects, 'avg_defects': batch_avg,
        'defect_rate': batch_defect_rate, 'project_avg': project_avg,
        'proj_defect_rate': proj_defect_rate, 'traffic': batch_traffic,
        'delta_val': delta_val, 'delta_label': delta_label,
        'median_defects': round(batch_median, 1),
        'min_defects': batch_min, 'max_defects': batch_max,
        'items_inspected': ITEMS_PER_UNIT * batch_total_inspected,
    }

    # 6. Area breakdown scoped to batch cycles
    area_data = []
    if all_cycle_ids:
        ph = ','.join('?' * len(all_cycle_ids))
        area_query = (
            "SELECT at2.area_name AS area, COUNT(d.id) AS defect_count "
            "FROM defect d "
            "JOIN item_template it ON d.item_template_id = it.id "
            "JOIN category_template ct ON it.category_id = ct.id "
            "JOIN area_template at2 ON ct.area_id = at2.id "
            "WHERE d.tenant_id = ? AND d.status = 'open' "
            "AND d.unit_id IN (SELECT unit_id FROM batch_unit WHERE batch_id = ? AND removed_at IS NULL AND tenant_id = ?) "
            "AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup')) "
            "AND d.raised_cycle_id IN ({}) "
            "GROUP BY at2.area_name ORDER BY defect_count DESC"
        ).format(ph)
        area_raw = query_db(area_query, [tenant_id, batch_id, tenant_id] + all_cycle_ids)
        area_data = [dict(r) for r in area_raw]
    area_max = area_data[0]['defect_count'] if area_data else 1
    area_counts_sorted = sorted([a['defect_count'] for a in area_data])
    if area_counts_sorted:
        mid = len(area_counts_sorted) // 2
        area_median = area_counts_sorted[mid] if len(area_counts_sorted) % 2 else (area_counts_sorted[mid - 1] + area_counts_sorted[mid]) / 2
    else:
        area_median = 0

    # 7b. Area deep dive scoped to batch
    area_deep_dive = []
    dd_colours = ['#C8963E', '#3D6B8E']
    for idx, area_row in enumerate(area_data[:2]):
        area_name = area_row['area']
        if all_cycle_ids:
            ph = ','.join('?' * len(all_cycle_ids))
            dd_query = (
                "SELECT d.original_comment AS description, COUNT(*) AS count "
                "FROM defect d "
                "JOIN item_template it ON d.item_template_id = it.id "
                "JOIN category_template ct ON it.category_id = ct.id "
                "JOIN area_template at2 ON ct.area_id = at2.id "
                "WHERE d.tenant_id = ? AND d.status = 'open' "
                "AND d.unit_id IN (SELECT unit_id FROM batch_unit WHERE batch_id = ? AND removed_at IS NULL AND tenant_id = ?) "
                "AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup')) "
                "AND d.raised_cycle_id IN ({}) "
                "AND at2.area_name = ? "
                "GROUP BY d.original_comment ORDER BY count DESC LIMIT 3"
            ).format(ph)
            dd_raw = [dict(r) for r in query_db(dd_query, [tenant_id, batch_id, tenant_id] + all_cycle_ids + [area_name])]
        else:
            dd_raw = []
        max_dd = dd_raw[0]['count'] if dd_raw else 1
        for d in dd_raw:
            d['bar_pct'] = round(d['count'] / max_dd * 100)
        area_pct = round(area_row['defect_count'] / batch_total_defects * 100, 1) if batch_total_defects > 0 else 0
        area_deep_dive.append({'area': area_name, 'total': area_row['defect_count'], 'pct': area_pct, 'colour': dd_colours[idx], 'defects': dd_raw})
    dd_callout = ''
    if area_deep_dive and area_deep_dive[0]['defects']:
        a1 = area_deep_dive[0]
        d1 = a1['defects'][0]
        dd_callout = 'The most frequent defect in {} is {} ({} occurrences).'.format(a1['area'].title(), d1['description'].lower(), d1['count'])
        if len(area_deep_dive) >= 2 and area_deep_dive[1]['defects']:
            a2 = area_deep_dive[1]
            d2 = a2['defects'][0]
            dd_callout += ' In {}, {} leads with {} occurrences.'.format(a2['area'].title(), d2['description'].lower(), d2['count'])

    # 7c. Top defect types scoped to batch
    top_defects = []
    td_median = 0
    if all_cycle_ids:
        ph = ','.join('?' * len(all_cycle_ids))
        td_query = (
            "SELECT original_comment AS description, COUNT(*) AS cnt "
            "FROM defect "
            "WHERE tenant_id = ? AND status = 'open' "
            "AND unit_id IN (SELECT unit_id FROM batch_unit WHERE batch_id = ? AND removed_at IS NULL AND tenant_id = ?) "
            "AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = defect.unit_id AND i2.cycle_id = defect.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup')) "
            "AND raised_cycle_id IN ({}) "
            "GROUP BY original_comment ORDER BY cnt DESC LIMIT 10"
        ).format(ph)
        top_defects = [dict(r) for r in query_db(td_query, [tenant_id, batch_id, tenant_id] + all_cycle_ids)]
    td_counts = sorted([d['cnt'] for d in top_defects])
    if td_counts:
        mid = len(td_counts) // 2
        td_median = td_counts[mid] if len(td_counts) % 2 else (td_counts[mid - 1] + td_counts[mid]) / 2

    # 7d. Recurring defects scoped to batch
    recurring = []
    if all_cycle_ids:
        ph = ','.join('?' * len(all_cycle_ids))
        rec_query = (
            "SELECT d.original_comment, "
            "COUNT(d.id) AS cnt, COUNT(DISTINCT d.unit_id) AS unit_count "
            "FROM defect d "
            "JOIN unit_real u ON d.unit_id = u.id "
            "WHERE d.tenant_id = ? AND d.status = 'open' "
            "AND d.unit_id IN (SELECT unit_id FROM batch_unit WHERE batch_id = ? AND removed_at IS NULL AND tenant_id = ?) "
            "AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup')) "
            "AND d.raised_cycle_id IN ({}) "
            "GROUP BY d.original_comment "
            "HAVING unit_count >= 2 ORDER BY cnt DESC LIMIT 10"
        ).format(ph)
        recurring = [dict(r) for r in query_db(rec_query, [tenant_id, batch_id, tenant_id] + all_cycle_ids)]
        if recurring:
            top_comments = [r['original_comment'] for r in recurring]
            cat_ph = ','.join('?' * len(top_comments))
            batch_ph = ','.join('?' * len(all_cycle_ids))
            cat_raw = query_db(
                "SELECT d.original_comment, ct.category_name, COUNT(d.id) AS cat_cnt "
                "FROM defect d "
                "JOIN item_template it ON d.item_template_id = it.id "
                "JOIN category_template ct ON it.category_id = ct.id "
                "WHERE d.tenant_id = ? AND d.status = 'open' "
                "AND d.unit_id IN (SELECT unit_id FROM batch_unit WHERE batch_id = ? AND removed_at IS NULL AND tenant_id = ?) "
                "AND d.raised_cycle_id IN ({}) "
                "AND d.original_comment IN ({}) "
                "AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup')) "
                "GROUP BY d.original_comment, ct.category_name "
                "ORDER BY d.original_comment, cat_cnt DESC"
            .format(batch_ph, cat_ph), [tenant_id, batch_id, tenant_id] + all_cycle_ids + top_comments)
            from collections import defaultdict as _dd
            cat_map = _dd(list)
            for row in cat_raw:
                cat_map[row['original_comment']].append({'cat': row['category_name'], 'cnt': row['cat_cnt']})
            for r in recurring:
                r['cat_breakdown'] = cat_map.get(r['original_comment'], [])

    # 7e. Category/trade breakdown scoped to batch
    category_data = []
    cat_median = 0
    if all_cycle_ids:
        ph = ','.join('?' * len(all_cycle_ids))
        cat_query = (
            "SELECT ct.category_name AS category, COUNT(d.id) AS count "
            "FROM defect d "
            "JOIN item_template it ON d.item_template_id = it.id "
            "JOIN category_template ct ON it.category_id = ct.id "
            "WHERE d.tenant_id = ? AND d.status = 'open' "
            "AND d.unit_id IN (SELECT unit_id FROM batch_unit WHERE batch_id = ? AND removed_at IS NULL AND tenant_id = ?) "
            "AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup')) "
            "AND d.raised_cycle_id IN ({}) "
            "GROUP BY ct.category_name ORDER BY count DESC"
        ).format(ph)
        category_data = [dict(r) for r in query_db(cat_query, [tenant_id, batch_id, tenant_id] + all_cycle_ids)]
    cat_counts = sorted([c['count'] for c in category_data])
    if cat_counts:
        mid = len(cat_counts) // 2
        cat_median = cat_counts[mid] if len(cat_counts) % 2 else (cat_counts[mid - 1] + cat_counts[mid]) / 2

    # 7. All batches for selector
    all_batches = [dict(r) for r in query_db("""
        SELECT id, name, status FROM inspection_batch
        WHERE tenant_id = ? AND status IN ('reviewed', 'complete') ORDER BY created_at DESC
    """, [tenant_id])]

    return render_template('analytics/batch_detail.html',
                           batch=batch, zones=zones, kpis=kpis,
                           area_data=area_data, area_max=area_max,
                           area_colours=AREA_COLOURS, project_avg=project_avg,
                           area_median=area_median,
                           area_deep_dive=area_deep_dive, dd_callout=dd_callout,
                           top_defects=top_defects, td_median=td_median,
                           recurring=recurring,
                           category_data=category_data, cat_median=cat_median,
                           q1=q1, q3=q3,
                           all_batches=all_batches, floor_labels=FLOOR_LABELS,
                           batch_id=batch_id)


@analytics_bp.route('/<block_slug>/<int:floor>')
@require_manager
def block_floor_detail(block_slug, floor):
    """Block+Floor detail page - unit table, round comparison, area breakdown, top defects."""
    tenant_id = session.get('tenant_id', 'MONOGRAPH')
    block = _slug_to_block(block_slug)
    floor_label = FLOOR_LABELS.get(floor, 'Floor {}'.format(floor))
    label = '{} {}'.format(block, floor_label)

    # 1. All cycles for this block+floor
    cycles = [dict(r) for r in query_db("""
        SELECT id, cycle_number
        FROM inspection_cycle
        WHERE block = ? AND floor = ? AND tenant_id = ? AND id NOT LIKE 'test-%'
        ORDER BY cycle_number
    """, [block, floor, tenant_id])]
    cycle_ids = [c['id'] for c in cycles]
    max_round = max((c['cycle_number'] for c in cycles), default=0)

    if not cycle_ids:
        return render_template('analytics/block_floor_detail.html',
                               block=block, floor=floor, label=label,
                               has_data=False, units=[], rounds=[],
                               rectification=[], rect_totals={}, rect_callout='',
                               area_data=[], area_deep_dive=[], dd_callout='',
                               top_defects=[], summary={}, td_median=0)

    # Build cycle_id -> round_number lookup
    cycle_round_map = {c['id']: c['cycle_number'] for c in cycles}

    # 2. Unit status table
    units_raw = [dict(r) for r in query_db("""
        SELECT u.id as unit_id, u.unit_number,
            i.id as inspection_id, i.status as insp_status,
            i.cycle_id, i.inspector_name,
            i.cycle_number as round_number,
            COUNT(d.id) as defect_count
        FROM unit_real u
        JOIN inspection i ON i.unit_id = u.id AND i.tenant_id = u.tenant_id
        LEFT JOIN defect d ON d.unit_id = u.id AND d.raised_cycle_id = i.cycle_id
            AND d.status = 'open' AND d.tenant_id = u.tenant_id
        WHERE u.block = ? AND u.floor = ? AND u.tenant_id = ?
        AND i.cycle_id NOT LIKE 'test-%'
        GROUP BY u.id, i.cycle_id
        ORDER BY u.unit_number, i.cycle_number
    """, [block, floor, tenant_id])]

    # Keep only the latest round per unit for the table
    unit_latest = {}
    for r in units_raw:
        un = r['unit_number']
        if un not in unit_latest or r['round_number'] > unit_latest[un]['round_number']:
            unit_latest[un] = r

    # Status display mapping
    status_display = {
        'not_started': 'Not Started',
        'in_progress': 'In Progress',
        'submitted': 'Submitted',
        'reviewed': 'Reviewed',
        'pending_followup': 'Signed Off',
        'approved': 'Approved',
        'certified': 'Certified',
        'closed': 'Closed',
    }
    status_colour = {
        'not_started': 'bg-gray-100 text-gray-600',
        'in_progress': 'bg-blue-100 text-blue-700',
        'submitted': 'bg-yellow-100 text-yellow-700',
        'reviewed': 'bg-purple-100 text-purple-700',
        'pending_followup': 'bg-emerald-100 text-emerald-700',
        'approved': 'bg-emerald-100 text-emerald-700',
        'certified': 'bg-emerald-200 text-emerald-800',
        'closed': 'bg-gray-200 text-gray-700',
    }

    units = []
    for un in sorted(unit_latest.keys()):
        r = unit_latest[un]
        u_defect_rate = round(r['defect_count'] / ITEMS_PER_UNIT * 100, 1) if ITEMS_PER_UNIT > 0 else 0
        units.append({
            'unit_id': r['unit_id'],
            'unit_number': un,
            'round_number': r['round_number'],
            'insp_status': r['insp_status'],
            'status_label': status_display.get(r['insp_status'], r['insp_status']),
            'status_colour': status_colour.get(r['insp_status'], 'bg-gray-100 text-gray-600'),
            'defect_count': r['defect_count'],
            'defect_rate': u_defect_rate,
            'inspector_name': r['inspector_name'] or '-',
        })
    # Sort worst-first
    units.sort(key=lambda u: u['defect_count'], reverse=True)

    # Summary stats
    total_units = len(units)
    total_defects = sum(u['defect_count'] for u in units)
    avg_defects = round(total_defects / total_units, 1) if total_units > 0 else 0
    items_inspected = ITEMS_PER_UNIT * total_units
    defect_rate = round(total_defects / items_inspected * 100, 1) if items_inspected > 0 else 0

    # Median calculation
    counts_list = sorted(u['defect_count'] for u in units)
    if not counts_list:
        median_defects = 0
    elif len(counts_list) % 2 == 0:
        median_defects = round((counts_list[len(counts_list)//2-1] + counts_list[len(counts_list)//2]) / 2, 1)
    else:
        median_defects = counts_list[len(counts_list)//2]

    summary = {
        'total_units': total_units,
        'total_defects': total_defects,
        'avg_defects': avg_defects,
        'defect_rate': defect_rate,
        'items_inspected': items_inspected,
        'max_round': max_round,
        'median_defects': median_defects,
    }

    # 3. Round comparison (only if max_round > 1)
    rounds = []
    if max_round > 1:
        rounds_raw = [dict(r) for r in query_db("""
            SELECT i.cycle_number as round_number,
                COUNT(DISTINCT d.id) as total_defects,
                COUNT(DISTINCT i.unit_id) as units_inspected,
                COUNT(DISTINCT CASE WHEN d.status = 'open' THEN d.id END) as still_open,
                COUNT(DISTINCT CASE WHEN d.status = 'cleared' THEN d.id END) as cleared
            FROM inspection_cycle ic
            JOIN inspection i ON i.cycle_id = ic.id AND i.tenant_id = ic.tenant_id
            LEFT JOIN defect d ON d.raised_cycle_id = ic.id AND d.tenant_id = ic.tenant_id
            WHERE ic.block = ? AND ic.floor = ? AND ic.tenant_id = ?
            AND ic.id NOT LIKE 'test-%'
            GROUP BY ic.cycle_number
            ORDER BY ic.cycle_number
        """, [block, floor, tenant_id])]

        for r in rounds_raw:
            r['avg_defects'] = round(r['total_defects'] / r['units_inspected'], 1) if r['units_inspected'] > 0 else 0
            clearance_base = r['total_defects']
            r['clearance_pct'] = round(r['cleared'] / clearance_base * 100, 1) if clearance_base > 0 else 0
        rounds = rounds_raw

    # 3b. Rectification tracker (only when re-inspected units exist)
    rectification = []
    rect_totals = {}
    rect_callout = ''

    if max_round > 1:
        prev_cycle_ids = [c['id'] for c in cycles if c['cycle_number'] == max_round - 1]
        latest_cycle_ids = [c['id'] for c in cycles if c['cycle_number'] == max_round]

        if prev_cycle_ids and latest_cycle_ids:
            ph_latest = ','.join('?' * len(latest_cycle_ids))
            ph_prev = ','.join('?' * len(prev_cycle_ids))

            # Find units inspected in the latest round
            re_units = [dict(r) for r in query_db("""
                SELECT DISTINCT u.id as unit_id, u.unit_number
                FROM inspection i
                JOIN unit_real u ON i.unit_id = u.id
                WHERE i.cycle_id IN ({}) AND i.tenant_id = ?
                ORDER BY u.unit_number
            """.format(ph_latest), latest_cycle_ids + [tenant_id])]

            for unit in re_units:
                uid = unit['unit_id']

                # Previous round: total raised, all cleared
                prev = dict(query_db("""
                    SELECT COUNT(*) as raised,
                        SUM(CASE WHEN status = 'cleared' THEN 1 ELSE 0 END) as cleared,
                        SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as still_open
                    FROM defect WHERE unit_id = ? AND raised_cycle_id IN ({}) AND tenant_id = ?
                """.format(ph_prev), [uid] + prev_cycle_ids + [tenant_id], one=True))

                # All defects raised in latest round
                new_all = dict(query_db("""
                    SELECT COUNT(*) as cnt FROM defect
                    WHERE unit_id = ? AND raised_cycle_id IN ({}) AND tenant_id = ?
                """.format(ph_latest),
                    [uid] + latest_cycle_ids + [tenant_id], one=True))

                # Total currently open for this unit (across all rounds)
                open_cnt = dict(query_db("""
                    SELECT COUNT(*) as cnt FROM defect
                    WHERE unit_id = ? AND status = 'open' AND tenant_id = ?
                """, [uid, tenant_id], one=True))

                prev_raised = prev['raised']
                prev_cleared = prev['cleared'] or 0
                clearance_pct = round(prev_cleared / prev_raised * 100, 1) if prev_raised > 0 else 0

                rectification.append({
                    'unit_number': unit['unit_number'],
                    'prev_raised': prev_raised,
                    'prev_cleared': prev_cleared,
                    'new_defects': new_all['cnt'],
                    'total_open': open_cnt['cnt'],
                    'clearance_pct': clearance_pct,
                })

            if rectification:
                sum_prev = sum(r['prev_raised'] for r in rectification)
                sum_cleared = sum(r['prev_cleared'] for r in rectification)
                sum_new = sum(r['new_defects'] for r in rectification)
                sum_open = sum(r['total_open'] for r in rectification)
                total_pct = round(sum_cleared / sum_prev * 100, 1) if sum_prev > 0 else 0

                net_imp = sum_cleared - sum_new
                rect_totals = {
                    'prev_raised': sum_prev,
                    'prev_cleared': sum_cleared,
                    'new_defects': sum_new,
                    'total_open': sum_open,
                    'clearance_pct': total_pct,
                    'net_improvement': net_imp,
                }

                rect_callout = 'Of {} defects raised on re-inspected units in Cycle {}, {} ({:.1f}%) have been rectified.'.format(
                    sum_prev, max_round - 1, sum_cleared, total_pct)
                if sum_new > 0:
                    rect_callout += ' {} new defects identified in Cycle {}.'.format(sum_new, max_round)

    # 4. Area breakdown (all open defects in this block+floor)
    area_data_raw = [dict(r) for r in query_db("""
        SELECT at2.area_name as area, COUNT(d.id) as defect_count
        FROM defect d
        JOIN unit_real u ON d.unit_id = u.id
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at2 ON ct.area_id = at2.id
        WHERE u.block = ? AND u.floor = ? AND d.tenant_id = ?
        AND d.status = 'open' AND d.raised_cycle_id NOT LIKE 'test-%'
        AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
        GROUP BY at2.area_name
        ORDER BY defect_count DESC
    """, [block, floor, tenant_id])]

    max_area_count = area_data_raw[0]['defect_count'] if area_data_raw else 1
    for a in area_data_raw:
        a['bar_pct'] = round(a['defect_count'] / max_area_count * 100)
        a['pct'] = round(a['defect_count'] / total_defects * 100, 1) if total_defects > 0 else 0
        a['colour'] = AREA_COLOURS.get(a['area'], '#9ca3af')

    # 5. Area Deep Dive - top 3 defects in top 2 areas
    area_deep_dive = []
    dd_colours = ['#C8963E', '#3D6B8E']
    for idx, area_row in enumerate(area_data_raw[:2]):
        area_name = area_row['area']
        area_defects = [dict(r) for r in query_db("""
            SELECT d.original_comment as description, COUNT(*) as count
            FROM defect d
            JOIN unit_real u ON d.unit_id = u.id
            JOIN item_template it ON d.item_template_id = it.id
            JOIN category_template ct ON it.category_id = ct.id
            JOIN area_template at2 ON ct.area_id = at2.id
            WHERE u.block = ? AND u.floor = ? AND d.tenant_id = ?
            AND d.status = 'open' AND d.raised_cycle_id NOT LIKE 'test-%'
            AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
            AND at2.area_name = ?
            GROUP BY d.original_comment
            ORDER BY count DESC
            LIMIT 3
        """, [block, floor, tenant_id, area_name])]
        max_dd = area_defects[0]['count'] if area_defects else 1
        for d in area_defects:
            d['bar_pct'] = round(d['count'] / max_dd * 100)
        area_deep_dive.append({
            'area': area_name, 'total': area_row['defect_count'],
            'pct_of_total': area_row['pct'], 'colour': dd_colours[idx],
            'defects': area_defects,
        })

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

    # 6. Top defect types (scoped to block+floor)
    top_defects = [dict(r) for r in query_db("""
        SELECT d.original_comment as description, COUNT(*) as count
        FROM defect d
        JOIN unit_real u ON d.unit_id = u.id
        WHERE u.block = ? AND u.floor = ? AND d.tenant_id = ?
        AND d.status = 'open' AND d.raised_cycle_id NOT LIKE 'test-%'
        AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
        GROUP BY d.original_comment
        ORDER BY count DESC
        LIMIT 10
    """, [block, floor, tenant_id])]

    max_defect_count = top_defects[0]['count'] if top_defects else 1
    for d in top_defects:
        d['bar_pct'] = round(d['count'] / max_defect_count * 100)
        d['pct'] = round(d['count'] / total_defects * 100, 1) if total_defects > 0 else 0

    # Top defect median for colour coding
    td_counts = sorted(d['count'] for d in top_defects) if top_defects else []
    if not td_counts:
        td_median = 0
    elif len(td_counts) % 2 == 0:
        td_median = round((td_counts[len(td_counts)//2-1] + td_counts[len(td_counts)//2]) / 2, 1)
    else:
        td_median = td_counts[len(td_counts)//2]

    return render_template('analytics/block_floor_detail.html',
                           block=block, floor=floor, label=label,
                           block_slug=block_slug,
                           has_data=True,
                           units=units,
                           rounds=rounds,
                           rectification=rectification,
                           rect_totals=rect_totals,
                           rect_callout=rect_callout,
                           area_data=area_data_raw,
                           area_deep_dive=area_deep_dive,
                           dd_callout=dd_callout,
                           top_defects=top_defects,
                           td_median=td_median,
                           summary=summary)


# ============================================================
# BLOCK DETAIL - Compare zones within a block
# ============================================================

@analytics_bp.route('/<block_slug>')
@require_manager
def block_detail(block_slug):
    """Block detail page - compare zones (floors) within a block."""
    tenant_id = session.get('tenant_id', 'MONOGRAPH')
    block = _slug_to_block(block_slug)

    # Get all zones in this block with stats
    zones_raw = [dict(r) for r in query_db("""
        SELECT u.floor,
            COUNT(DISTINCT u.id) as total_units,
            COUNT(DISTINCT CASE WHEN d.status = 'open' THEN d.id END) as open_defects,
            MAX(i.cycle_number) as max_round,
            COUNT(DISTINCT CASE WHEN d.status = 'cleared' THEN d.id END) as rectified
        FROM unit_real u
        LEFT JOIN inspection i ON i.unit_id = u.id AND i.tenant_id = u.tenant_id
        LEFT JOIN defect d ON d.unit_id = u.id AND d.tenant_id = u.tenant_id
        WHERE u.block = ? AND u.tenant_id = ?
        AND u.unit_number NOT LIKE 'TEST%'
        GROUP BY u.floor
        ORDER BY u.floor
    """, [block, tenant_id])]

    zones = []
    total_units = 0
    total_defects = 0
    for z in zones_raw:
        units = z['total_units']
        defects = z['open_defects']
        if units == 0:
            continue
        total_units += units
        total_defects += defects
        avg = round(defects / units, 1) if units > 0 else 0
        rate = round(defects / (units * ITEMS_PER_UNIT) * 100, 1) if units > 0 else 0
        zones.append({
            'floor': z['floor'],
            'floor_label': FLOOR_LABELS.get(z['floor'], 'Floor {}'.format(z['floor'])),
            'total_units': units,
            'open_defects': defects,
            'avg_defects': avg,
            'defect_rate': rate,
            'max_round': z['max_round'] or 1,
            'rectified': z['rectified'] or 0,
            'slug': '{}/{}'.format(block_slug, z['floor']),
        })

    # Block-wide area breakdown
    area_data = [dict(r) for r in query_db("""
        SELECT at2.area_name as area, COUNT(d.id) as defect_count
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at2 ON ct.area_id = at2.id
        JOIN unit_real u ON d.unit_id = u.id
        WHERE d.status = 'open' AND d.tenant_id = ? AND u.block = ?
        AND u.unit_number NOT LIKE 'TEST%'
        AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
        GROUP BY at2.area_name
        ORDER BY defect_count DESC
    """, [tenant_id, block])]

    if area_data:
        max_area = area_data[0]['defect_count']
        for a in area_data:
            a['pct'] = round(a['defect_count'] / total_defects * 100, 1) if total_defects > 0 else 0
            a['bar_pct'] = round(a['defect_count'] / max_area * 100) if max_area > 0 else 0
            a['colour'] = AREA_COLOURS.get(a['area'], '#6B6B6B')

    # Block-wide top defect types
    top_defects = [dict(r) for r in query_db("""
        SELECT d.original_comment as description, COUNT(*) as count
        FROM defect d
        JOIN unit_real u ON d.unit_id = u.id
        WHERE d.status = 'open' AND d.tenant_id = ? AND u.block = ?
        AND u.unit_number NOT LIKE 'TEST%'
        AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
        GROUP BY d.original_comment
        ORDER BY count DESC
        LIMIT 10
    """, [tenant_id, block])]

    return render_template('analytics/block_detail.html',
                           block=block,
                           block_slug=block_slug,
                           zones=zones,
                           total_units=total_units,
                           total_defects=total_defects,
                           area_data=area_data,
                           top_defects=top_defects,
                           has_data=len(zones) > 0)


# ============================================================
# DRILL-DOWN EXPLORE ENGINE
# ============================================================

@analytics_bp.route('/explore')
@require_manager
def explore():
    """Universal drill-down: any number on any page links here with filters.
    Every combination of filters shows ranked children + defect breakdown."""
    tenant_id = session.get('tenant_id', 'MONOGRAPH')

    # Parse filters
    f_block = request.args.get('block')
    f_floor = request.args.get('floor', type=int)
    f_unit = request.args.get('unit')
    f_area = request.args.get('area')
    f_category = request.args.get('category')
    f_round = request.args.get('round', type=int)

    # Build WHERE clauses and params
    where_parts = ["d.tenant_id = ?", "d.status = 'open'", "u.unit_number NOT LIKE 'TEST%'", "EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))"]
    params = [tenant_id]

    if f_block:
        where_parts.append("u.block = ?")
        params.append(f_block)
    if f_floor is not None:
        where_parts.append("u.floor = ?")
        params.append(f_floor)
    if f_unit:
        where_parts.append("u.unit_number = ?")
        params.append(f_unit)
    if f_area:
        where_parts.append("at2.area_name = ?")
        params.append(f_area)
    if f_category:
        where_parts.append("ct.category_name = ?")
        params.append(f_category)
    if f_round:
        where_parts.append("d.raised_cycle_number = ?")
        params.append(f_round)

    where_sql = " AND ".join(where_parts)

    # Base FROM clause (always the same full join chain)
    from_sql = """
        FROM defect d
        JOIN unit_real u ON d.unit_id = u.id
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at2 ON ct.area_id = at2.id
    """

    # Summary for current scope
    summary = dict(query_db("""
        SELECT COUNT(DISTINCT d.id) as total_defects,
               COUNT(DISTINCT u.id) as total_units,
               COUNT(DISTINCT u.block) as block_count
        {} WHERE {}
    """.format(from_sql, where_sql), params, one=True))

    avg_per_unit = round(summary['total_defects'] / summary['total_units'], 1) if summary['total_units'] > 0 else 0
    summary['avg_per_unit'] = avg_per_unit

    # ---- LOCATION BREAKDOWN ----
    # Show the next level of location hierarchy the user hasn't filtered to yet
    location_data = []
    location_level = None

    if not f_block:
        # Show blocks
        location_level = 'block'
        location_data = [dict(r) for r in query_db("""
            SELECT u.block as name, COUNT(DISTINCT d.id) as defects,
                   COUNT(DISTINCT u.id) as units
            {} WHERE {}
            GROUP BY u.block ORDER BY defects DESC
        """.format(from_sql, where_sql), params)]
    elif f_floor is None:
        # Show floors within block
        location_level = 'floor'
        location_data = [dict(r) for r in query_db("""
            SELECT u.floor as name, COUNT(DISTINCT d.id) as defects,
                   COUNT(DISTINCT u.id) as units
            {} WHERE {}
            GROUP BY u.floor ORDER BY defects DESC
        """.format(from_sql, where_sql), params)]
        for loc in location_data:
            loc['display'] = FLOOR_LABELS.get(loc['name'], 'Floor {}'.format(loc['name']))
    elif not f_unit:
        # Show units within zone
        location_level = 'unit'
        location_data = [dict(r) for r in query_db("""
            SELECT u.unit_number as name, COUNT(DISTINCT d.id) as defects
            {} WHERE {}
            GROUP BY u.unit_number ORDER BY defects DESC
        """.format(from_sql, where_sql), params)]

    # Add percentages and bar widths to location data
    if location_data:
        max_loc = location_data[0]['defects']
        for loc in location_data:
            loc['pct'] = round(loc['defects'] / summary['total_defects'] * 100, 1) if summary['total_defects'] > 0 else 0
            loc['bar_pct'] = round(loc['defects'] / max_loc * 100) if max_loc > 0 else 0
            if 'display' not in loc:
                loc['display'] = str(loc['name'])

    # ---- DEFECT BREAKDOWN ----
    # Show the next level of defect hierarchy the user hasn't filtered to yet
    defect_data = []
    defect_level = None

    if not f_area:
        # Show areas
        defect_level = 'area'
        defect_data = [dict(r) for r in query_db("""
            SELECT at2.area_name as name, COUNT(DISTINCT d.id) as defects,
                   COUNT(DISTINCT u.id) as units
            {} WHERE {}
            GROUP BY at2.area_name ORDER BY defects DESC
        """.format(from_sql, where_sql), params)]
    elif not f_category:
        # Show categories within area
        defect_level = 'category'
        defect_data = [dict(r) for r in query_db("""
            SELECT ct.category_name as name, COUNT(DISTINCT d.id) as defects,
                   COUNT(DISTINCT u.id) as units
            {} WHERE {}
            GROUP BY ct.category_name ORDER BY defects DESC
        """.format(from_sql, where_sql), params)]
    else:
        # Show individual defect descriptions within category
        defect_level = 'item'
        defect_data = [dict(r) for r in query_db("""
            SELECT d.original_comment as name, COUNT(DISTINCT d.id) as defects,
                   COUNT(DISTINCT u.id) as units
            {} WHERE {}
            GROUP BY d.original_comment ORDER BY defects DESC
        """.format(from_sql, where_sql), params)]

    # Add colours and bar widths to defect data
    if defect_data:
        max_def = defect_data[0]['defects']
        for dd in defect_data:
            dd['pct'] = round(dd['defects'] / summary['total_defects'] * 100, 1) if summary['total_defects'] > 0 else 0
            dd['bar_pct'] = round(dd['defects'] / max_def * 100) if max_def > 0 else 0
            dd['colour'] = AREA_COLOURS.get(dd['name'], '#6B6B6B')

    # ---- BREADCRUMB ----
    breadcrumbs = [{'label': 'Project', 'url': '/analytics/explore'}]
    crumb_params = {}

    if f_block:
        crumb_params['block'] = f_block
        breadcrumbs.append({
            'label': f_block,
            'url': '/analytics/explore?block={}'.format(f_block)
        })
    if f_floor is not None:
        crumb_params['floor'] = f_floor
        breadcrumbs.append({
            'label': FLOOR_LABELS.get(f_floor, 'Floor {}'.format(f_floor)),
            'url': '/analytics/explore?block={}&floor={}'.format(f_block, f_floor)
        })
    if f_unit:
        crumb_params['unit'] = f_unit
        breadcrumbs.append({
            'label': 'Unit {}'.format(f_unit),
            'url': '/analytics/explore?block={}&floor={}&unit={}'.format(f_block, f_floor, f_unit)
        })
    if f_area:
        # Area breadcrumb preserves location filters
        area_url_parts = ['area={}'.format(f_area)]
        if f_block:
            area_url_parts.append('block={}'.format(f_block))
        if f_floor is not None:
            area_url_parts.append('floor={}'.format(f_floor))
        if f_unit:
            area_url_parts.append('unit={}'.format(f_unit))
        breadcrumbs.append({
            'label': f_area.title(),
            'url': '/analytics/explore?{}'.format('&'.join(area_url_parts))
        })
    if f_category:
        cat_url_parts = ['area={}&category={}'.format(f_area, f_category)]
        if f_block:
            cat_url_parts.append('block={}'.format(f_block))
        if f_floor is not None:
            cat_url_parts.append('floor={}'.format(f_floor))
        breadcrumbs.append({
            'label': f_category,
            'url': '/analytics/explore?{}'.format('&'.join(cat_url_parts))
        })

    # Build title
    title_parts = []
    if f_block:
        title_parts.append(f_block)
    if f_floor is not None:
        title_parts.append(FLOOR_LABELS.get(f_floor, 'Floor {}'.format(f_floor)))
    if f_unit:
        title_parts.append('Unit {}'.format(f_unit))
    if f_area:
        title_parts.append(f_area.title())
    if f_category:
        title_parts.append(f_category)
    title = ' > '.join(title_parts) if title_parts else 'All Blocks'

    # Build link helpers for template
    def _explore_url(**extra):
        """Build explore URL preserving current filters + adding extras."""
        p = {}
        if f_block:
            p['block'] = f_block
        if f_floor is not None:
            p['floor'] = f_floor
        if f_unit:
            p['unit'] = f_unit
        if f_area:
            p['area'] = f_area
        if f_category:
            p['category'] = f_category
        if f_round:
            p['round'] = f_round
        p.update(extra)
        return '/analytics/explore?' + '&'.join('{}={}'.format(k, v) for k, v in p.items())

    # Pre-build URLs for location drill-down
    for loc in location_data:
        if location_level == 'block':
            loc['url'] = _explore_url(block=loc['name'])
        elif location_level == 'floor':
            loc['url'] = _explore_url(floor=loc['name'])
        elif location_level == 'unit':
            loc['url'] = _explore_url(unit=loc['name'])

    # Pre-build URLs for defect drill-down
    for dd in defect_data:
        if defect_level == 'area':
            dd['url'] = _explore_url(area=dd['name'])
        elif defect_level == 'category':
            dd['url'] = _explore_url(category=dd['name'])
        else:
            dd['url'] = None  # Item level = bottom, no further drill

    return render_template('analytics/explore.html',
                           title=title,
                           breadcrumbs=breadcrumbs,
                           summary=summary,
                           location_data=location_data,
                           location_level=location_level,
                           defect_data=defect_data,
                           defect_level=defect_level,
                           filters={'block': f_block, 'floor': f_floor, 'unit': f_unit,
                                    'area': f_area, 'category': f_category, 'round': f_round})





# ============================================================
# RECTIFICATION ANALYTICS
# ============================================================

def _build_rectification_data():
    """Build data dict for rectification analytics template."""
    tenant_id = session.get('tenant_id', 'MONOGRAPH')

    # 1. Identify re-inspected units (units with inspection in C2+ cycle)
    reinspected_units = [dict(r) for r in query_db("""
        SELECT DISTINCT i.unit_id, u.unit_number, u.block, u.floor
        FROM inspection i
        JOIN unit_real u ON i.unit_id = u.id
        WHERE i.tenant_id = ? AND i.cycle_number > 1
        AND i.cycle_id NOT LIKE 'test-%'
        AND i.status IN ('reviewed','approved','certified','pending_followup')
    """, [tenant_id])]

    if not reinspected_units:
        return dict(has_data=False, kpis={}, zones=[], areas=[],
                     area_max=1, trades=[], trade_max=1,
                     stubborn=[], new_defects=[], c2_new_count=0,
                     units=[], turnaround={})

    reinspected_unit_ids = [u['unit_id'] for u in reinspected_units]
    ph = ','.join(['?'] * len(reinspected_unit_ids))

    # 2. C1 defects on re-inspected units
    c1_defects = [dict(r) for r in query_db("""
        SELECT d.id, d.unit_id, d.item_template_id, d.status,
            d.original_comment, d.created_at, d.cleared_at,
            d.raised_cycle_id, d.cleared_cycle_id,
            u.block, u.floor
        FROM defect d
        WHERE d.tenant_id = ? AND d.raised_cycle_number = 1
        AND d.unit_id IN ({ph})
        AND d.raised_cycle_id NOT LIKE 'test-%'
    """.format(ph=ph), [tenant_id] + reinspected_unit_ids)]

    c1_total = len(c1_defects)
    c1_cleared = sum(1 for d in c1_defects if d['status'] == 'cleared')
    c1_still_open = sum(1 for d in c1_defects if d['status'] == 'open')

    # 3. New defects raised in C2+ cycles
    c2_new_defects = [dict(r) for r in query_db("""
        SELECT d.id, d.unit_id, d.item_template_id, d.original_comment,
            d.status, d.created_at, d.defect_type,
            u.unit_number, u.block, u.floor,
            at2.area_name, ct.category_name
        FROM defect d
        JOIN unit_real u ON d.unit_id = u.id
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at2 ON ct.area_id = at2.id
        WHERE d.tenant_id = ? AND d.raised_cycle_number > 1
        AND d.unit_id IN ({ph})
        AND d.raised_cycle_id NOT LIKE 'test-%'
    """.format(ph=ph), [tenant_id] + reinspected_unit_ids)]

    c2_new_count = len(c2_new_defects)

    # 4. Turnaround time
    turnaround_raw = query_db("""
        SELECT
            ROUND(AVG(julianday(d.cleared_at) - julianday(d.created_at)), 1) AS avg_days,
            ROUND(MIN(julianday(d.cleared_at) - julianday(d.created_at)), 1) AS min_days,
            ROUND(MAX(julianday(d.cleared_at) - julianday(d.created_at)), 1) AS max_days,
            COUNT(*) as sample_size
        FROM defect d
        WHERE d.tenant_id = ? AND d.status = 'cleared'
        AND d.cleared_at IS NOT NULL AND d.created_at IS NOT NULL
        AND d.unit_id IN ({ph})
    """.format(ph=ph), [tenant_id] + reinspected_unit_ids, one=True)
    turnaround = dict(turnaround_raw) if turnaround_raw else {}

    # 5. KPI strip
    clearance_pct = round(c1_cleared / c1_total * 100, 1) if c1_total > 0 else 0
    net_improvement = c1_cleared - c2_new_count
    net_pct = round(net_improvement / c1_total * 100, 1) if c1_total > 0 else 0
    total_inspected = query_db("SELECT COUNT(DISTINCT unit_id) AS cnt FROM inspection WHERE tenant_id = ? AND status IN ('reviewed','approved','certified','pending_followup')", [tenant_id], one=True)
    total_inspected_count = dict(total_inspected)['cnt'] if total_inspected else 0

    max_cycle_row = query_db(
        "SELECT MAX(d.raised_cycle_number) AS max_cycle FROM inspection i "
        "WHERE i.tenant_id = ? AND i.unit_id IN ({ph}) "
        "AND i.cycle_id NOT LIKE 'test-%'".format(ph=ph),
        [tenant_id] + reinspected_unit_ids, one=True)
    max_cycle_num = int(dict(max_cycle_row)['max_cycle']) if max_cycle_row and dict(max_cycle_row)['max_cycle'] else 2

    kpis = {
        'total_inspected': total_inspected_count,
        'clearance_rate': clearance_pct,
        'units_reinspected': len(reinspected_units),
        'c1_reviewed': c1_total,
        'c1_cleared': c1_cleared,
        'c1_still_open': c1_still_open,
        'new_in_c2': c2_new_count,
        'net_improvement': net_improvement,
        'net_pct': net_pct,
        'avg_rect_days': turnaround.get('avg_days') or 0,
        'avg_rect_days_available': bool(turnaround.get('avg_days')),
        'max_cycle_num': max_cycle_num,
    }

    # 6. Scorecard by zone
    zone_map = {}
    for d in c1_defects:
        key = (d['block'], d['floor'])
        if key not in zone_map:
            zone_map[key] = {'block': d['block'], 'floor': d['floor'],
                             'c1_total': 0, 'cleared': 0, 'still_open': 0, 'new_c2': 0}
        zone_map[key]['c1_total'] += 1
        if d['status'] == 'cleared':
            zone_map[key]['cleared'] += 1
        else:
            zone_map[key]['still_open'] += 1

    for d in c2_new_defects:
        key = (d['block'], d['floor'])
        if key not in zone_map:
            zone_map[key] = {'block': d['block'], 'floor': d['floor'],
                             'c1_total': 0, 'cleared': 0, 'still_open': 0, 'new_c2': 0}
        zone_map[key]['new_c2'] += 1

    zone_cycle_raw = query_db(
        "SELECT u.block, u.floor, MAX(i.cycle_number) AS max_cycle "
        "FROM inspection i "
        "WHERE i.tenant_id = ? AND i.unit_id IN ({ph}) "
        "AND i.cycle_id NOT LIKE 'test-%' "
        "AND i.status IN ('reviewed','approved','certified','pending_followup') "
        "GROUP BY u.block, u.floor".format(ph=ph),
        [tenant_id] + reinspected_unit_ids)
    zone_cycle_map = {(r['block'], r['floor']): int(r['max_cycle']) for r in zone_cycle_raw}

    zones = sorted(zone_map.values(), key=lambda z: (z['block'], z['floor']))
    for z in zones:
        z['clearance_pct'] = round(z['cleared'] / z['c1_total'] * 100, 1) if z['c1_total'] > 0 else 0
        z['net'] = z['cleared'] - z['new_c2']
        z['effective_pct'] = round(z['net'] / z['c1_total'] * 100, 1) if z['c1_total'] > 0 else 0
        z['floor_label'] = FLOOR_LABELS.get(z['floor'], 'Floor {}'.format(z['floor']))
        z['slug'] = _block_to_slug(z['block'])
        z['cycle_num'] = zone_cycle_map.get((z['block'], z['floor']), 2)
        z['remaining'] = z['still_open'] + z['new_c2']

    # Median clearance rate for zone grid traffic-light
    _clearance_vals = sorted(z['clearance_pct'] for z in zones if z['c1_total'] > 0)
    if _clearance_vals:
        _mid = len(_clearance_vals) // 2
        zone_median_clearance = _clearance_vals[_mid] if len(_clearance_vals) % 2 else round((_clearance_vals[_mid - 1] + _clearance_vals[_mid]) / 2, 1)
    else:
        zone_median_clearance = 0

    # 7. Rectification by area
    area_c1 = [dict(r) for r in query_db("""
        SELECT at2.area_name AS area,
            SUM(CASE WHEN d.status = 'cleared' THEN 1 ELSE 0 END) as cleared,
            SUM(CASE WHEN d.status = 'open' THEN 1 ELSE 0 END) as still_open
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at2 ON ct.area_id = at2.id
        WHERE d.tenant_id = ? AND d.raised_cycle_number = 1
        AND d.unit_id IN ({ph})
        AND d.raised_cycle_id NOT LIKE 'test-%'
        GROUP BY at2.area_name
        ORDER BY (SUM(CASE WHEN d.status = 'cleared' THEN 1 ELSE 0 END)
                 + SUM(CASE WHEN d.status = 'open' THEN 1 ELSE 0 END)) DESC
    """.format(ph=ph), [tenant_id] + reinspected_unit_ids)]

    area_new = [dict(r) for r in query_db("""
        SELECT at2.area_name AS area, COUNT(d.id) as new_count
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at2 ON ct.area_id = at2.id
        WHERE d.tenant_id = ? AND d.raised_cycle_number > 1
        AND d.unit_id IN ({ph})
        AND d.raised_cycle_id NOT LIKE 'test-%'
        GROUP BY at2.area_name
    """.format(ph=ph), [tenant_id] + reinspected_unit_ids)]
    area_new_map = {r['area']: r['new_count'] for r in area_new}

    areas = []
    for a in area_c1:
        total_c1 = a['cleared'] + a['still_open']
        new = area_new_map.get(a['area'], 0)
        eff = a['cleared'] - new
        eff_pct = round(eff / total_c1 * 100, 1) if total_c1 > 0 else 0
        areas.append({
            'area': a['area'], 'c1_total': total_c1,
            'cleared': a['cleared'], 'still_open': a['still_open'], 'new': new,
            'clearance_pct': round(a['cleared'] / total_c1 * 100, 1) if total_c1 > 0 else 0,
            'effective_pct': eff_pct, 'net': eff,
            'colour': AREA_COLOURS.get(a['area'], '#6B6B6B'),
        })
    area_max = max((a['c1_total'] + a['new'] for a in areas), default=1)

    # 8. Rectification by trade/category
    trade_c1 = [dict(r) for r in query_db("""
        SELECT ct.category_name AS trade,
            SUM(CASE WHEN d.status = 'cleared' THEN 1 ELSE 0 END) as cleared,
            SUM(CASE WHEN d.status = 'open' THEN 1 ELSE 0 END) as still_open
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        WHERE d.tenant_id = ? AND d.raised_cycle_number = 1
        AND d.unit_id IN ({ph})
        AND d.raised_cycle_id NOT LIKE 'test-%'
        GROUP BY ct.category_name
        ORDER BY (SUM(CASE WHEN d.status = 'cleared' THEN 1 ELSE 0 END)
                 + SUM(CASE WHEN d.status = 'open' THEN 1 ELSE 0 END)) DESC
    """.format(ph=ph), [tenant_id] + reinspected_unit_ids)]

    trade_new = [dict(r) for r in query_db("""
        SELECT ct.category_name AS trade, COUNT(d.id) as new_count
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        WHERE d.tenant_id = ? AND d.raised_cycle_number > 1
        AND d.unit_id IN ({ph})
        AND d.raised_cycle_id NOT LIKE 'test-%'
        GROUP BY ct.category_name
    """.format(ph=ph), [tenant_id] + reinspected_unit_ids)]
    trade_new_map = {r['trade']: r['new_count'] for r in trade_new}

    trades = []
    for t in trade_c1:
        total_c1 = t['cleared'] + t['still_open']
        new = trade_new_map.get(t['trade'], 0)
        t_eff = t['cleared'] - new
        t_eff_pct = round(t_eff / total_c1 * 100, 1) if total_c1 > 0 else 0
        trades.append({
            'trade': t['trade'], 'c1_total': total_c1,
            'cleared': t['cleared'], 'still_open': t['still_open'], 'new': new,
            'clearance_pct': round(t['cleared'] / total_c1 * 100, 1) if total_c1 > 0 else 0,
            'effective_pct': t_eff_pct, 'net': t_eff,
        })
    trade_max = max((t['c1_total'] + t['new'] for t in trades), default=1)

    # 9. Stubborn defects (C1 open despite re-inspection)
    stubborn_raw = [dict(r) for r in query_db("""
        SELECT d.original_comment AS description,
            at2.area_name AS area, ct.category_name AS category,
            u.unit_number,
            CAST(julianday('now') - julianday(d.created_at) AS INTEGER) AS age_days
        FROM defect d
        JOIN unit_real u ON d.unit_id = u.id
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at2 ON ct.area_id = at2.id
        WHERE d.tenant_id = ? AND d.status = 'open'
        AND d.raised_cycle_number = 1
        AND d.unit_id IN ({ph})
        AND d.raised_cycle_id NOT LIKE 'test-%'
        ORDER BY age_days DESC
    """.format(ph=ph), [tenant_id] + reinspected_unit_ids)]

    stubborn_grouped = {}
    for s in stubborn_raw:
        desc = s['description']
        if desc not in stubborn_grouped:
            stubborn_grouped[desc] = {
                'description': desc, 'area': s['area'], 'category': s['category'],
                'units': [], 'max_age': 0
            }
        stubborn_grouped[desc]['units'].append(s['unit_number'])
        if s['age_days'] > stubborn_grouped[desc]['max_age']:
            stubborn_grouped[desc]['max_age'] = s['age_days']

    stubborn = sorted(stubborn_grouped.values(), key=lambda x: len(x['units']), reverse=True)

    # 10. New defects in C2 grouped by area
    new_by_area = {}
    for d in c2_new_defects:
        area = d['area_name']
        if area not in new_by_area:
            new_by_area[area] = []
        new_by_area[area].append({
            'description': d['original_comment'],
            'unit': d['unit_number'],
            'category': d['category_name'],
        })
    new_defects_grouped = [{'area': a, 'defect_list': items, 'count': len(items)}
                           for a, items in sorted(new_by_area.items(),
                                                  key=lambda x: len(x[1]), reverse=True)]

    # 11. Unit drill-down table
    unit_map = {}
    for d in c1_defects:
        uid = d['unit_id']
        if uid not in unit_map:
            uinfo = next((u for u in reinspected_units if u['unit_id'] == uid), None)
            unit_map[uid] = {
                'unit_id': uid,
                'unit_number': uinfo['unit_number'] if uinfo else '?',
                'block': uinfo['block'] if uinfo else '?',
                'floor': uinfo['floor'] if uinfo else 0,
                'c1_raised': 0, 'cleared': 0, 'still_open': 0, 'new_c2': 0,
            }
        unit_map[uid]['c1_raised'] += 1
        if d['status'] == 'cleared':
            unit_map[uid]['cleared'] += 1
        else:
            unit_map[uid]['still_open'] += 1

    for d in c2_new_defects:
        uid = d['unit_id']
        if uid in unit_map:
            unit_map[uid]['new_c2'] += 1

    units_table = sorted(unit_map.values(), key=lambda u: u['unit_number'])
    for u in units_table:
        u['clearance_pct'] = round(u['cleared'] / u['c1_raised'] * 100, 1) if u['c1_raised'] > 0 else 0
        u['net'] = u['cleared'] - u['new_c2']
        u['effective_pct'] = round(u['net'] / u['c1_raised'] * 100, 1) if u['c1_raised'] > 0 else 0
        u['floor_label'] = FLOOR_LABELS.get(u['floor'], 'Floor {}'.format(u['floor']))

    # Build grid: blocks x floors
    grid_blocks = sorted(set(z['block'] for z in zones))
    grid_floors = sorted(set(z['floor'] for z in zones))
    zone_lookup = {}
    for z in zones:
        zone_lookup.setdefault(z['block'], {})[z['floor']] = z
    zone_grid = {
        'blocks': grid_blocks,
        'floors': grid_floors,
        'floor_labels': {f: FLOOR_LABELS.get(f, 'Floor {}'.format(f)) for f in grid_floors},
        'lookup': zone_lookup,
    }

    return dict(has_data=True,
                kpis=kpis,
                zones=zones,
                zone_grid=zone_grid,
                zone_median_clearance=zone_median_clearance,
                areas=areas, area_max=area_max,
                trades=trades, trade_max=trade_max,
                stubborn=stubborn,
                new_defects=new_defects_grouped, c2_new_count=c2_new_count,
                units=units_table,
                turnaround=turnaround)


@analytics_bp.route('/rectification')
@require_manager
def rectification():
    """Rectification Command Centre."""
    return render_template('analytics/rectification.html', **_build_rectification_data())


@analytics_bp.route('/rectification/report')
@require_manager
def rectification_report():
    """View rectification analytics as printable report."""
    import datetime
    data = _build_rectification_data()
    data['is_pdf'] = False
    data['report_date'] = datetime.datetime.now().strftime('%d %B %Y')
    data['logo_b64'] = ''
    return render_template('analytics/rectification_pdf.html', **data)


@analytics_bp.route('/rectification/pdf')
@require_manager
def rectification_pdf():
    """Download rectification analytics as PDF."""
    from app.services.pdf_playwright import html_to_pdf
    from flask import current_app
    import datetime, base64, os as _os
    data = _build_rectification_data()
    data['is_pdf'] = True
    data['report_date'] = datetime.datetime.now().strftime('%d %B %Y')
    logo_path = _os.path.join(current_app.static_folder, 'monograph_logo.jpg')
    if _os.path.exists(logo_path):
        with open(logo_path, 'rb') as f:
            data['logo_b64'] = base64.b64encode(f.read()).decode()
    else:
        data['logo_b64'] = ''
    html_str = render_template('analytics/rectification_pdf.html', **data)
    pdf_bytes = html_to_pdf(html_str)
    resp = make_response(pdf_bytes)
    resp.headers['Content-Type'] = 'application/pdf'
    resp.headers['Content-Disposition'] = 'attachment; filename=Rectification_Analytics_{}.pdf'.format(
        datetime.datetime.now().strftime('%Y%m%d'))
    return resp


@analytics_bp.route('/legacy')
@require_manager
def dashboard_legacy():
    """LEGACY: Analytics Dashboard - cycle-based view. Will be removed."""
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
            "SELECT COUNT(DISTINCT u.id) FROM unit_real u JOIN inspection i ON i.unit_id = u.id WHERE i.tenant_id = ? AND i.cycle_id NOT LIKE 'test-%' AND i.status IN ('reviewed','approved','certified','pending_followup')",
            [tenant_id], one=True)[0]
        total_defects = query_db(
            "SELECT COUNT(*) FROM defect WHERE tenant_id = ? AND status = 'open' AND raised_cycle_id NOT LIKE 'test-%'",
            [tenant_id], one=True)[0]
        avg_defects = round(total_defects / total_units, 1) if total_units > 0 else 0

        unit_defect_counts = query_db(
            "SELECT u.unit_number, COUNT(*) as cnt FROM defect d JOIN unit_real u ON d.unit_id = u.id "
            "WHERE d.tenant_id = ? AND d.status = 'open' AND d.raised_cycle_id NOT LIKE 'test-%' AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup')) GROUP BY d.unit_id ORDER BY cnt DESC",
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
            "AND i.status IN ('reviewed','approved','certified','pending_followup') "
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
            "WHERE d.tenant_id = ? AND d.status = 'open' AND d.raised_cycle_id NOT LIKE 'test-%' "
            "AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup')) "
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
            "WHERE d.tenant_id = ? AND d.status = 'open' AND d.raised_cycle_id NOT LIKE 'test-%' "
            "AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup')) "
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
            "WHERE d.tenant_id = ? AND d.status = 'open' AND d.raised_cycle_id NOT LIKE 'test-%' "
            "AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup')) "
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
            "AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup')) "
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
            "AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup')) "
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
            "FROM defect d JOIN unit_real u ON d.unit_id = u.id "
            "JOIN inspection i ON i.unit_id = u.id AND i.cycle_id = d.raised_cycle_id "
            "WHERE d.tenant_id = ? AND d.status = 'open' AND d.raised_cycle_id NOT LIKE 'test-%' "
            "AND i.status IN ('reviewed','approved','certified','pending_followup') "
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
            "FROM defect d JOIN unit_real u ON d.unit_id = u.id "
            "JOIN item_template it ON d.item_template_id = it.id "
            "JOIN category_template ct ON it.category_id = ct.id "
            "WHERE d.tenant_id = ? AND d.status = 'open' AND d.raised_cycle_id NOT LIKE 'test-%' "
            "AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup')) "
            "GROUP BY d.original_comment HAVING COUNT(DISTINCT u.id) >= 3 "
            "ORDER BY cnt DESC", [tenant_id])

        # Inspector stats
        inspector_stats = query_db(
            "SELECT i.inspector_name, COUNT(DISTINCT i.unit_id) as units_inspected, "
            "COUNT(d.id) as total_defects, "
            "ROUND(CAST(COUNT(d.id) AS FLOAT) / COUNT(DISTINCT i.unit_id), 1) as avg_per_unit "
            "FROM inspection i LEFT JOIN defect d ON d.unit_id = i.unit_id "
            "AND d.raised_cycle_id = i.cycle_id AND d.status = 'open' "
            "WHERE i.tenant_id = ? AND i.cycle_id NOT LIKE 'test-%' AND i.status IN ('reviewed','approved','certified','pending_followup') GROUP BY i.inspector_name ORDER BY avg_per_unit DESC",
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
            "AND i.status IN ('reviewed','approved','certified','pending_followup') "
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
            "AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup')) "
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
            "FROM inspection i JOIN unit_real u ON i.unit_id = u.id "
            "LEFT JOIN defect d ON d.unit_id = u.id AND d.status = 'open' "
            "AND d.raised_cycle_id = i.cycle_id "
            "WHERE i.tenant_id = ? AND i.cycle_id NOT LIKE 'test-%' "
            "AND i.status IN ('reviewed','approved','certified','pending_followup') "
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
            "WHERE d.tenant_id = ? AND d.status = 'open' AND d.raised_cycle_id NOT LIKE 'test-%' "
            "AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup')) "
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
        FROM unit_real u
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
        JOIN unit_real u ON d.unit_id = u.id
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
        JOIN unit_real u ON d.unit_id = u.id
        JOIN inspection i ON i.unit_id = u.id AND i.cycle_id = d.raised_cycle_id
        WHERE d.raised_cycle_id = ? AND d.tenant_id = ? AND d.status = 'open'
        GROUP BY u.unit_number, i.inspector_name
        ORDER BY cnt DESC
    """, [selected_cycle_id, tenant_id])

    # --- 5. HEATMAP: AREA x UNIT ---
    heatmap_raw = query_db("""
        SELECT u.unit_number, at.area_name, COUNT(*) as cnt
        FROM defect d
        JOIN unit_real u ON d.unit_id = u.id
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
        JOIN unit_real u ON d.unit_id = u.id
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
        AND i.status IN ('reviewed','approved','certified','pending_followup')
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
        FROM inspection i JOIN unit_real u ON i.unit_id = u.id
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




def _to_dicts(rows):
    """Convert sqlite3.Row results to plain dicts."""
    return [dict(r) for r in rows]


def _to_dict(row):
    """Convert a single sqlite3.Row to a plain dict."""
    return dict(row) if row else None
def _build_unified_report_data():
    """Build data for unified project report.
    Merges dashboard queries (progress, rectification, zone cards)
    with report visual data (donut SVG, logo base64).
    Returns dict with all template variables, or None if no data.
    """
    import base64, os, math, statistics
    from flask import current_app, session

    tenant_id = session.get('tenant_id', 'MONOGRAPH')

    def _hex_to_rgba(hex_colour, alpha=0.15):
        h = hex_colour.lstrip('#')
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return 'rgba({},{},{},{})'.format(r, g, b, alpha)

    # Unit counts per block+floor
    unit_counts_raw = query_db("""
        SELECT u.block, u.floor, COUNT(DISTINCT u.id) as total_units
        FROM unit_real u
        WHERE u.tenant_id = ? AND u.unit_number NOT LIKE 'TEST%'
        GROUP BY u.block, u.floor
        ORDER BY u.block, u.floor
    """, [tenant_id])
    unit_counts = [dict(r) for r in unit_counts_raw]

    if not unit_counts:
        return None

    # Open defects per block+floor
    defect_counts_raw = query_db("""
        SELECT u.block, u.floor, COUNT(d.id) as open_defects
        FROM defect d
        JOIN unit_real u ON d.unit_id = u.id
        WHERE d.tenant_id = ? AND d.status = 'open'
        AND d.raised_cycle_id NOT LIKE 'test-%'
        AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
        GROUP BY u.block, u.floor
    """, [tenant_id])
    defect_map = {}
    for r in defect_counts_raw:
        defect_map[(r['block'], r['floor'])] = r['open_defects']

    # Inspected units per block+floor
    inspected_zone_raw = query_db("""
        SELECT u.block, u.floor, COUNT(DISTINCT i.unit_id) as inspected
        FROM inspection i
        JOIN unit_real u ON i.unit_id = u.id
        WHERE i.tenant_id = ? AND i.cycle_id NOT LIKE 'test-%'
        AND i.status IN ('reviewed','approved','certified','pending_followup')
        GROUP BY u.block, u.floor
    """, [tenant_id])
    inspected_zone_map = {}
    for r in inspected_zone_raw:
        inspected_zone_map[(r['block'], r['floor'])] = r['inspected']

    # Certified counts per block+floor
    certified_raw = query_db("""
        SELECT u.block, u.floor, COUNT(DISTINCT i.unit_id) as certified
        FROM inspection i
        JOIN unit_real u ON i.unit_id = u.id
        WHERE i.tenant_id = ? AND i.status = 'certified'
        AND i.cycle_id NOT LIKE 'test-%'
        GROUP BY u.block, u.floor
    """, [tenant_id])
    certified_map = {}
    for r in certified_raw:
        certified_map[(r['block'], r['floor'])] = r['certified']

    # Round breakdown per block+floor
    rounds_raw = query_db("""
        SELECT u.block, u.floor, i.cycle_number as round_number,
            COUNT(DISTINCT i.unit_id) as units_inspected
        FROM inspection i
        JOIN unit_real u ON i.unit_id = u.id
        WHERE i.tenant_id = ? AND i.cycle_id NOT LIKE 'test-%'
        AND i.status IN ('reviewed','approved','certified','pending_followup')
        GROUP BY u.block, u.floor, i.cycle_number
        ORDER BY u.block, u.floor, i.cycle_number
    """, [tenant_id])
    rounds_map = {}
    for r in rounds_raw:
        key = (r['block'], r['floor'])
        if key not in rounds_map:
            rounds_map[key] = []
        rounds_map[key].append({
            'round_number': r['round_number'],
            'units_inspected': r['units_inspected'],
        })

    # Build zone cards
    zone_cards = []
    total_units_project = 0
    total_defects_project = 0
    total_certified_project = 0

    for uc in unit_counts:
        key = (uc['block'], uc['floor'])
        total_units = uc['total_units']
        open_defects = defect_map.get(key, 0)
        rounds = rounds_map.get(key, [])
        certified = certified_map.get(key, 0)
        inspected = inspected_zone_map.get(key, 0)
        max_round = max((r['round_number'] for r in rounds), default=0)
        avg_defects = round(open_defects / inspected, 1) if inspected > 0 else 0
        items_inspected = ITEMS_PER_UNIT * inspected
        defect_rate = round(open_defects / items_inspected * 100, 1) if items_inspected > 0 else 0
        floor_label = FLOOR_LABELS.get(uc['floor'], 'Floor {}'.format(uc['floor']))

        zone_cards.append({
            'block': uc['block'],
            'floor': uc['floor'],
            'floor_label': floor_label,
            'label': '{} {}'.format(uc['block'], floor_label),
            'total_units': total_units,
            'inspected': inspected,
            'open_defects': open_defects,
            'avg_defects': avg_defects,
            'defect_rate': defect_rate,
            'rounds': rounds,
            'max_round': max_round,
            'certified': certified,
        })

        total_units_project += total_units
        total_defects_project += open_defects
        total_certified_project += certified

    # Project overview
    units_inspected_raw = query_db("""
        SELECT COUNT(DISTINCT i.unit_id) as inspected
        FROM inspection i
        JOIN unit_real u ON u.id = i.unit_id
        WHERE i.tenant_id = ? AND i.cycle_id NOT LIKE 'test-%'
        AND i.status IN ('reviewed','approved','certified','pending_followup')
    """, [tenant_id], one=True)
    units_inspected = units_inspected_raw['inspected'] if units_inspected_raw else 0
    items_inspected_total = ITEMS_PER_UNIT * units_inspected

    project = {
        'total_units': total_units_project,
        'units_inspected': units_inspected,
        'project_total': PROJECT_TOTAL_UNITS,
        'pct_complete': round(units_inspected / PROJECT_TOTAL_UNITS * 100) if PROJECT_TOTAL_UNITS > 0 else 0,
        'open_defects': total_defects_project,
        'avg_defects': round(total_defects_project / units_inspected, 1) if units_inspected > 0 else 0,
        'defect_rate': round(total_defects_project / items_inspected_total * 100, 1) if items_inspected_total > 0 else 0,
        'certified': total_certified_project,
    }

    project['avg_defects_inspected'] = project['avg_defects']
    project['defect_rate_inspected'] = project['defect_rate']
    project['items_inspected'] = items_inspected_total

    # Median, min, max defects per unit
    unit_defect_counts_raw = query_db("""
        SELECT COUNT(d.id) as defect_count
        FROM inspection i
        JOIN unit_real u ON i.unit_id = u.id
        LEFT JOIN defect d ON d.unit_id = u.id AND d.status = 'open'
            AND d.raised_cycle_id NOT LIKE 'test-%' AND d.tenant_id = u.tenant_id
            AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
        WHERE i.tenant_id = ? AND i.cycle_id NOT LIKE 'test-%'
        AND i.status IN ('reviewed','approved','certified','pending_followup')
        AND u.unit_number NOT LIKE 'TEST%'
        GROUP BY u.id
        ORDER BY defect_count
    """, [tenant_id])
    unit_counts_list = [r['defect_count'] for r in unit_defect_counts_raw]
    if unit_counts_list:
        n = len(unit_counts_list)
        median_val = unit_counts_list[n // 2] if n % 2 else (unit_counts_list[n // 2 - 1] + unit_counts_list[n // 2]) / 2
        project['median_defects'] = round(median_val, 1)
        project['min_defects'] = unit_counts_list[0]
        project['max_defects'] = unit_counts_list[-1]
    else:
        project['median_defects'] = 0
        project['min_defects'] = 0
        project['max_defects'] = 0

    # Rectification pulse
    r2_units_raw = query_db("""
        SELECT COUNT(DISTINCT i.unit_id) as r2_units
        FROM inspection i
        WHERE i.tenant_id = ? AND i.cycle_number > 1
        AND i.cycle_id NOT LIKE 'test-%' AND i.status IN ('reviewed','approved','certified','pending_followup')
    """, [tenant_id], one=True)

    rectification = None
    r2_units = r2_units_raw['r2_units'] if r2_units_raw else 0
    if r2_units > 0:
        rect_cleared = query_db("""
            SELECT COUNT(*) as total FROM defect d
            WHERE d.tenant_id = ? AND d.raised_cycle_id NOT LIKE 'test-%'
            AND d.status = 'cleared'
        """, [tenant_id], one=True)
        total_cleared = rect_cleared['total'] or 0 if rect_cleared else 0

        r2_new_raw = query_db("""
            SELECT COUNT(*) as new_defects FROM defect d
            WHERE d.tenant_id = ? AND d.raised_cycle_number > 1
            AND d.raised_cycle_id NOT LIKE 'test-%' AND d.status = 'open'
        """, [tenant_id], one=True)
        r2_new = r2_new_raw['new_defects'] or 0 if r2_new_raw else 0

        net_imp = total_cleared - r2_new
        rectification = {
            'r2_units': r2_units,
            'rectified': total_cleared,
            'new_defects': r2_new,
            'net_improvement': net_imp,
        }

    # Defect density grid
    grid_blocks = sorted(set(c['block'] for c in zone_cards if c['inspected'] > 0))
    grid_floors = sorted(set(c['floor'] for c in zone_cards if c['inspected'] > 0))
    block_floor_grid = {}
    for c in zone_cards:
        if c['inspected'] > 0:
            if c['block'] not in block_floor_grid:
                block_floor_grid[c['block']] = {}
            block_floor_grid[c['block']][c['floor']] = {
                'avg': c['avg_defects'],
                'defects': c['open_defects'],
                'units': c['inspected'],
                'defect_rate': c['defect_rate'],
            }

    grid_median = project['avg_defects']

    # Area distribution + donut SVG
    area_data_raw = [dict(r) for r in query_db("""
        SELECT at2.area_name as area, COUNT(d.id) as defect_count
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at2 ON ct.area_id = at2.id
        WHERE d.tenant_id = ? AND d.status = 'open'
            AND d.raised_cycle_id NOT LIKE 'test-%%'
            AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
        GROUP BY at2.area_name ORDER BY defect_count DESC
    """, [tenant_id])]

    area_max = area_data_raw[0]['defect_count'] if area_data_raw else 1
    area_colours = ['#C8963E', '#3D6B8E', '#4A7C59', '#C44D3F', '#7B6B8D', '#5A8A7A', '#B07D4B']

    circumference = 439.82
    offset = 0
    for a in area_data_raw:
        pct = a['defect_count'] / total_defects_project if total_defects_project > 0 else 0
        a['pct'] = round(pct * 100, 1)
        a['dash'] = round(pct * circumference, 2)
        a['offset'] = round(offset, 2)
        offset += a['dash']
    for a in area_data_raw:
        mid_frac = (a['offset'] + a['dash'] / 2) / circumference
        angle = mid_frac * 2 * math.pi - math.pi / 2
        a['pct_x'] = round(100 + 70 * math.cos(angle), 1)
        a['pct_y'] = round(100 + 70 * math.sin(angle), 1)

    area_counts_sorted = sorted([a['defect_count'] for a in area_data_raw])
    if area_counts_sorted:
        mid = len(area_counts_sorted) // 2
        area_median = area_counts_sorted[mid] if len(area_counts_sorted) % 2 else (area_counts_sorted[mid - 1] + area_counts_sorted[mid]) / 2
    else:
        area_median = 0

    area_top2_sum = sum(a['defect_count'] for a in area_data_raw[:2]) if len(area_data_raw) >= 2 else 0
    area_top2_pct = round(area_top2_sum / total_defects_project * 100) if total_defects_project > 0 else 0
    area_top2_names = [a['area'].title() for a in area_data_raw[:2]] if len(area_data_raw) >= 2 else []

    # Area deep dive
    area_deep_dive = []
    dd_colours = ['#C8963E', '#3D6B8E']
    for idx, area_row in enumerate(area_data_raw[:2]):
        area_name = area_row['area']
        area_defects = [dict(r) for r in query_db("""
            SELECT d.original_comment AS description, COUNT(*) AS count
            FROM defect d
            JOIN item_template it ON d.item_template_id = it.id
            JOIN category_template ct ON it.category_id = ct.id
            JOIN area_template at2 ON ct.area_id = at2.id
            WHERE d.tenant_id = ? AND d.status = 'open'
            AND d.raised_cycle_id NOT LIKE 'test-%'
            AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
            AND at2.area_name = ?
            GROUP BY d.original_comment
            ORDER BY count DESC
            LIMIT 3
        """, [tenant_id, area_name])]
        max_dd = area_defects[0]['count'] if area_defects else 1
        for d in area_defects:
            d['bar_pct'] = round(d['count'] / max_dd * 100)
        area_pct = round(area_row['defect_count'] / total_defects_project * 100, 1) if total_defects_project > 0 else 0
        area_deep_dive.append({
            'area': area_name,
            'total': area_row['defect_count'],
            'pct': area_pct,
            'colour': dd_colours[idx],
            'defects': area_defects,
        })

    dd_callout = ''
    if len(area_deep_dive) >= 1 and area_deep_dive[0]['defects']:
        a1 = area_deep_dive[0]
        d1 = a1['defects'][0]
        dd_callout = 'The most frequent defect in {} is {} ({} occurrences).'.format(
            a1['area'].title(), d1['description'].lower(), d1['count'])
        if len(area_deep_dive) >= 2 and area_deep_dive[1]['defects']:
            a2 = area_deep_dive[1]
            d2 = a2['defects'][0]
            dd_callout += ' In {}, {} leads with {} occurrences.'.format(
                a2['area'].title(), d2['description'].lower(), d2['count'])

    # Top defect types
    top_defects = [dict(r) for r in query_db("""
        SELECT original_comment AS description, COUNT(*) AS cnt
        FROM defect
        WHERE tenant_id = ? AND status = 'open'
        AND raised_cycle_id NOT LIKE 'test-%'
        AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = defect.unit_id AND i2.cycle_id = defect.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
        GROUP BY original_comment
        ORDER BY cnt DESC
        LIMIT 10
    """, [tenant_id])]

    td_max = top_defects[0]['cnt'] if top_defects else 1
    td_counts = sorted([d['cnt'] for d in top_defects])
    if td_counts:
        mid = len(td_counts) // 2
        td_median = td_counts[mid] if len(td_counts) % 2 else (td_counts[mid - 1] + td_counts[mid]) / 2
    else:
        td_median = 0

    # Systemic issues
    recurring_raw = query_db("""
        SELECT d.original_comment,
            COUNT(d.id) AS cnt,
            COUNT(DISTINCT d.unit_id) AS unit_count,
            GROUP_CONCAT(DISTINCT u.unit_number) AS affected_units
        FROM defect d
        JOIN unit_real u ON d.unit_id = u.id
        WHERE d.tenant_id = ? AND d.status = 'open'
        AND d.raised_cycle_id NOT LIKE 'test-%'
        AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
        GROUP BY d.original_comment
        HAVING unit_count >= 3
        ORDER BY cnt DESC
        LIMIT 10
    """, [tenant_id])
    recurring = [dict(r) for r in recurring_raw]
    if recurring:
        top_comments = [r['original_comment'] for r in recurring]
        placeholders = ','.join('?' * len(top_comments))
        cat_raw = query_db("""
            SELECT d.original_comment, ct.category_name, COUNT(d.id) AS cat_cnt
            FROM defect d
            JOIN item_template it ON d.item_template_id = it.id
            JOIN category_template ct ON it.category_id = ct.id
            WHERE d.tenant_id = ? AND d.status = 'open'
            AND d.raised_cycle_id NOT LIKE 'test-%'
            AND d.original_comment IN ({})
            AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
            GROUP BY d.original_comment, ct.category_name
            ORDER BY d.original_comment, cat_cnt DESC
        """.format(placeholders), [tenant_id] + top_comments)
        from collections import defaultdict
        cat_map = defaultdict(list)
        for row in cat_raw:
            cat_map[row['original_comment']].append({'cat': row['category_name'], 'cnt': row['cat_cnt']})
        for r in recurring:
            r['cat_breakdown'] = cat_map.get(r['original_comment'], [])

    # Defects by trade
    category_data = [dict(r) for r in query_db("""
        SELECT ct.category_name AS category, COUNT(d.id) AS count
        FROM defect d
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        WHERE d.tenant_id = ? AND d.status = 'open'
        AND d.raised_cycle_id NOT LIKE 'test-%'
        AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
        GROUP BY ct.category_name
        ORDER BY count DESC
    """, [tenant_id])]

    cat_max = category_data[0]['count'] if category_data else 1
    cat_counts = sorted([c['count'] for c in category_data])
    if cat_counts:
        mid = len(cat_counts) // 2
        cat_median = cat_counts[mid] if len(cat_counts) % 2 else (cat_counts[mid - 1] + cat_counts[mid]) / 2
    else:
        cat_median = 0

    # Top 5 worst units
    worst_units = [dict(r) for r in query_db("""
        SELECT u.id as unit_id, u.unit_number, u.block, u.floor,
               COUNT(d.id) as defect_count
        FROM defect d
        JOIN unit_real u ON d.unit_id = u.id
        WHERE d.tenant_id = ? AND d.status = 'open'
        AND d.raised_cycle_id NOT LIKE 'test-%'
        AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
        GROUP BY u.id, u.unit_number, u.block, u.floor
        ORDER BY defect_count DESC
        LIMIT 5
    """, [tenant_id])]
    worst_sum = sum(u['defect_count'] for u in worst_units)
    worst_pct = round(worst_sum / total_defects_project * 100) if total_defects_project > 0 else 0
    worst_blocks = {}
    for u in worst_units:
        key = u['block'] + ' ' + FLOOR_LABELS.get(u['floor'], 'Floor ' + str(u['floor']))
        worst_blocks[key] = worst_blocks.get(key, 0) + 1
    worst_dominant = max(worst_blocks.items(), key=lambda x: x[1]) if worst_blocks else ('', 0)

    # Quartile banding for unit colouring in unified report
    all_unit_counts_ur = [dict(r)['defect_count'] for r in query_db("""
        SELECT COUNT(d.id) as defect_count
        FROM inspection i
        JOIN unit_real u ON i.unit_id = u.id
        LEFT JOIN defect d ON d.unit_id = i.unit_id
            AND d.raised_cycle_id = i.cycle_id
            AND d.status = 'open'
            AND d.tenant_id = i.tenant_id
        WHERE i.tenant_id = ?
        AND i.status IN ('reviewed','approved','certified','pending_followup')
        AND u.unit_number NOT LIKE 'TEST%'
        AND i.cycle_id NOT LIKE 'test-%'
        GROUP BY i.unit_id
    """, [tenant_id])]
    sorted_ur = sorted(all_unit_counts_ur) if all_unit_counts_ur else []
    if len(sorted_ur) >= 4:
        n_ur = len(sorted_ur)
        q1 = sorted_ur[n_ur // 4]
        q3 = sorted_ur[(n_ur * 3) // 4]
    elif sorted_ur:
        q1 = min(sorted_ur)
        q3 = max(sorted_ur)
    else:
        q1 = q3 = 0

    # Zone performance (ranked worst to best)
    active_zones = [c for c in zone_cards if c['inspected'] > 0]
    active_zones.sort(key=lambda x: x['avg_defects'], reverse=True)

    zone_avgs = [c['avg_defects'] for c in active_zones]
    if zone_avgs:
        zone_avgs_sorted = sorted(zone_avgs)
        n_z = len(zone_avgs_sorted)
        zone_median = zone_avgs_sorted[n_z // 2] if n_z % 2 else round((zone_avgs_sorted[n_z // 2 - 1] + zone_avgs_sorted[n_z // 2]) / 2, 1)
    else:
        zone_median = 0

    # Logo + signature
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

    # Completion forecast
    from datetime import date, timedelta
    _fc_raw = query_db("""
        SELECT MIN(inspection_date) as first_date,
               MAX(inspection_date) as last_date,
               COUNT(DISTINCT i.unit_id) as done
        FROM inspection i
        JOIN unit_real u ON u.id = i.unit_id
        WHERE i.tenant_id = ? AND i.cycle_id NOT LIKE 'test-%'
        AND i.status IN ('submitted','reviewed','approved','pending_followup','certified')
        AND i.inspection_date IS NOT NULL
        AND u.unit_number NOT LIKE 'TEST%'
        AND i.cycle_number = 1
    """, [tenant_id], one=True)
    forecast = None
    if _fc_raw and _fc_raw['first_date'] and _fc_raw['last_date'] and _fc_raw['done']:
        _first = date.fromisoformat(_fc_raw['first_date'])
        _last = date.fromisoformat(_fc_raw['last_date'])
        _done = _fc_raw['done']
        _elapsed = (_last - _first).days or 1
        _rate = _done / _elapsed
        _remaining = PROJECT_TOTAL_UNITS - _done
        _days_left = round(_remaining / _rate) if _rate > 0 else None
        _est = _last + timedelta(days=_days_left) if _days_left else None
        forecast = {
            'est_date': _est.strftime('%-d %b %Y') if _est else 'N/A',
            'rate': round(_rate, 1),
            'rate_week': round(_rate * 7, 1),
            'remaining': _remaining,
            'done': _done,
        }

    floor_map = {0: 'Ground', 1: '1st Floor', 2: '2nd Floor', 3: '3rd Floor'}
    report_date = __import__('datetime').datetime.utcnow().strftime('%d %B %Y')

    return {
        'project': project,
        'forecast': forecast,
        'rectification': rectification,
        'zone_cards': active_zones,
        'zone_median': zone_median,
        'grid_blocks': grid_blocks,
        'grid_floors': grid_floors,
        'block_floor_grid': block_floor_grid,
        'grid_median': grid_median,
        'area_data': area_data_raw,
        'area_max': area_max,
        'area_colours': area_colours,
        'area_median': area_median,
        'area_top2_pct': area_top2_pct,
        'area_top2_names': area_top2_names,
        'area_deep_dive': area_deep_dive,
        'dd_callout': dd_callout,
        'top_defects': top_defects,
        'td_max': td_max,
        'td_median': td_median,
        'recurring': recurring,
        'category_data': category_data,
        'cat_max': cat_max,
        'cat_median': cat_median,
        'floor_map': floor_map,
        'logo_b64': logo_b64,
        'sig_b64': sig_b64,
        'report_date': report_date,
        'worst_units': worst_units,
        'worst_pct': worst_pct,
        'worst_dominant_zone': worst_dominant[0],
        'worst_dominant_count': worst_dominant[1],
        'q1': q1,
        'q3': q3,
    }


@analytics_bp.route('/report/unified')
@require_manager
def unified_report_view():
    """Unified project report - HTML view."""
    data = _build_unified_report_data()
    if data is None:
        return "No inspection data available.", 404
    data['is_pdf'] = False
    return render_template('analytics/report_unified.html', **data)


@analytics_bp.route('/report/unified/pdf')
@require_manager
def unified_report_pdf():
    """Unified project report - PDF download via Playwright."""
    from app.services.pdf_playwright import html_to_pdf
    data = _build_unified_report_data()
    if data is None:
        return "No inspection data available.", 404
    data['is_pdf'] = True
    html_str = render_template('analytics/report_unified.html', **data)
    pdf_bytes = html_to_pdf(html_str)
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=PPSH_Project_Report_{}.pdf'.format(
        data['report_date'].replace(' ', '_'))
    return response


@analytics_bp.route('/report/batch/<batch_id>')
@require_manager
def batch_report_view(batch_id):
    """Batch inspection report - HTML view."""
    data = _build_batch_report_data(batch_id)
    if data is None:
        return "Batch not found or no data.", 404
    data['is_pdf'] = False
    return render_template('analytics/report_batch.html', **data)


@analytics_bp.route('/report/batch/<batch_id>/pdf')
@require_manager
def batch_report_pdf(batch_id):
    """Batch inspection report - PDF download via Playwright."""
    from app.services.pdf_playwright import html_to_pdf
    data = _build_batch_report_data(batch_id)
    if data is None:
        return "Batch not found or no data.", 404
    data['is_pdf'] = True
    html_str = render_template('analytics/report_batch.html', **data)
    pdf_bytes = html_to_pdf(html_str)
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    fname = 'PPSH_Batch_Report_{}_{}.pdf'.format(
        data['batch']['name'].replace(' ', '_'),
        data['report_date_slug'])
    response.headers['Content-Disposition'] = 'attachment; filename={}'.format(fname)
    return response


def _build_batch_report_data(batch_id):
    """Build data for batch inspection report.
    Returns dict with all template variables, or None if batch not found.
    """
    import base64, os
    from flask import current_app, session

    tenant_id = session.get('tenant_id', 'MONOGRAPH')
    reviewed_statuses = ('reviewed', 'approved', 'certified', 'pending_followup')

    # 1. Batch metadata
    batch_row = query_db("""
        SELECT ib.id, ib.name, ib.status, ib.created_at,
               COUNT(DISTINCT bu.id) as total_units
        FROM inspection_batch ib
        LEFT JOIN batch_unit bu ON bu.batch_id = ib.id AND bu.removed_at IS NULL
        WHERE ib.id = ? AND ib.tenant_id = ?
        GROUP BY ib.id
    """, [batch_id, tenant_id], one=True)
    if not batch_row:
        return None
    batch = dict(batch_row)

    # 2. Project average benchmark
    proj_avg_row = query_db("""
        SELECT AVG(sub.defect_count) as project_avg
        FROM (
            SELECT i.unit_id, COUNT(d.id) as defect_count
            FROM inspection i
            JOIN unit_real u ON i.unit_id = u.id
            LEFT JOIN defect d ON d.unit_id = i.unit_id
                AND d.raised_cycle_id = i.cycle_id
                AND d.status = 'open'
                AND d.tenant_id = i.tenant_id
            WHERE i.tenant_id = ?
            AND i.status IN ('reviewed','approved','certified','pending_followup')
            AND u.unit_number NOT LIKE 'TEST%'
            AND i.cycle_id NOT LIKE 'test-%'
            GROUP BY i.unit_id
        ) sub
    """, [tenant_id], one=True)
    project_avg_raw = proj_avg_row['project_avg'] or 0 if proj_avg_row and proj_avg_row['project_avg'] else 0
    project_avg = round(project_avg_raw, 1)
    proj_defect_rate = round(project_avg_raw / ITEMS_PER_UNIT * 100, 1) if project_avg_raw > 0 else 0

    # 3. Zones in this batch
    zones_raw = [dict(r) for r in query_db("""
        SELECT ic.block, ic.floor, ic.id as cycle_id, ic.cycle_number,
               COUNT(DISTINCT bu.unit_id) as zone_units
        FROM batch_unit bu
        JOIN inspection_cycle ic ON bu.cycle_id = ic.id
        WHERE bu.batch_id = ? AND bu.removed_at IS NULL AND bu.tenant_id = ?
        GROUP BY ic.block, ic.floor, ic.id, ic.cycle_number
        ORDER BY ic.block, ic.floor
    """, [batch_id, tenant_id])]
    all_cycle_ids = [z['cycle_id'] for z in zones_raw]

    if not all_cycle_ids:
        return None

    # 4. Build zone data
    zones = []
    batch_total_defects = 0
    batch_total_inspected = 0

    for z in zones_raw:
        cycle_id = z['cycle_id']
        block = z['block']
        floor = z['floor']
        cycle_number = z['cycle_number']

        unit_rows = [dict(r) for r in query_db("""
            SELECT u.unit_number, u.id as unit_id,
                   COUNT(d.id) as defect_count,
                   i.status as insp_status
            FROM batch_unit bu
            JOIN unit_real u ON bu.unit_id = u.id
            LEFT JOIN defect d ON d.unit_id = u.id
                AND d.raised_cycle_id = ?
                AND d.status = 'open'
                AND d.tenant_id = u.tenant_id
            LEFT JOIN inspection i ON i.unit_id = u.id AND i.cycle_id = ?
            WHERE bu.batch_id = ? AND bu.removed_at IS NULL
            AND bu.cycle_id = ? AND bu.tenant_id = ?
            GROUP BY u.id, u.unit_number, i.status
            ORDER BY u.unit_number
        """, [cycle_id, cycle_id, batch_id, cycle_id, tenant_id])]

        inspected_units = [u for u in unit_rows if u['insp_status'] in reviewed_statuses]
        zone_inspected = len(inspected_units)
        zone_defects = sum(u['defect_count'] for u in inspected_units)
        zone_avg = round(zone_defects / zone_inspected, 1) if zone_inspected > 0 else 0

        rectification = None
        if cycle_number > 1 and inspected_units:
            prev_cycle_row = query_db("""
                SELECT id FROM inspection_cycle
                WHERE block = ? AND floor = ? AND cycle_number = ? AND tenant_id = ?
            """, [block, floor, cycle_number - 1, tenant_id], one=True)
            if prev_cycle_row:
                prev_cycle_id = prev_cycle_row['id']
                unit_ids = [u['unit_id'] for u in inspected_units]
                ph = ','.join('?' * len(unit_ids))
                r1_row = query_db(
                    'SELECT COUNT(*) as cnt FROM defect WHERE raised_cycle_id = ? AND unit_id IN (' + ph + ') AND tenant_id = ?',
                    [prev_cycle_id] + unit_ids + [tenant_id], one=True)
                cleared_row = query_db(
                    'SELECT COUNT(*) as cnt FROM defect WHERE cleared_cycle_id = ? AND unit_id IN (' + ph + ') AND tenant_id = ?',
                    [cycle_id] + unit_ids + [tenant_id], one=True)
                new_row = query_db(
                    'SELECT COUNT(*) as cnt FROM defect WHERE raised_cycle_id = ? AND unit_id IN (' + ph + ') AND tenant_id = ?',
                    [cycle_id] + unit_ids + [tenant_id], one=True)
                r1_count = r1_row['cnt'] if r1_row else 0
                cleared_count = cleared_row['cnt'] if cleared_row else 0
                new_count = new_row['cnt'] if new_row else 0
                still_open = max(r1_count - cleared_count, 0)
                clearance_pct = round(cleared_count / r1_count * 100) if r1_count > 0 else 0
                rectification = {
                    'r1_raised': r1_count, 'cleared': cleared_count,
                    'new': new_count, 'still_open': still_open,
                    'clearance_pct': clearance_pct, 'zone_units': zone_inspected,
                }

        floor_label = FLOOR_LABELS.get(floor, 'Floor {}'.format(floor))
        zones.append({
            'block': block, 'floor': floor, 'floor_label': floor_label,
            'label': '{} {}'.format(block, floor_label),
            'cycle_id': cycle_id, 'cycle_number': cycle_number,
            'total_units': z['zone_units'], 'inspected': zone_inspected,
            'defects': zone_defects, 'avg': zone_avg,
            'units': unit_rows, 'rectification': rectification,
        })
        batch_total_defects += zone_defects
        batch_total_inspected += zone_inspected

    # 5. Batch KPIs + quartile banding
    batch_avg = round(batch_total_defects / batch_total_inspected, 1) if batch_total_inspected > 0 else 0
    batch_items = ITEMS_PER_UNIT * batch_total_inspected
    batch_defect_rate = round(batch_total_defects / batch_items * 100, 1) if batch_items > 0 else 0

    all_unit_counts = []
    for z in zones:
        for u in z['units']:
            if u['insp_status'] in reviewed_statuses:
                all_unit_counts.append(u['defect_count'])

    sorted_counts = sorted(all_unit_counts) if all_unit_counts else []
    if len(sorted_counts) >= 4:
        n = len(sorted_counts)
        q1 = sorted_counts[n // 4]
        q3 = sorted_counts[(n * 3) // 4]
    elif sorted_counts:
        q1 = min(sorted_counts)
        q3 = max(sorted_counts)
    else:
        q1 = q3 = 0

    if sorted_counts:
        n2 = len(sorted_counts)
        batch_median = sorted_counts[n2 // 2] if n2 % 2 else (sorted_counts[n2 // 2 - 1] + sorted_counts[n2 // 2]) / 2
        batch_min = sorted_counts[0]
        batch_max = sorted_counts[-1]
    else:
        batch_median = batch_min = batch_max = 0

    kpis = {
        'total_units': batch['total_units'], 'inspected': batch_total_inspected,
        'total_defects': batch_total_defects, 'avg_defects': batch_avg,
        'defect_rate': batch_defect_rate, 'project_avg': project_avg,
        'proj_defect_rate': proj_defect_rate,
        'median_defects': round(batch_median, 1),
        'min_defects': batch_min, 'max_defects': batch_max,
        'items_inspected': batch_items,
        'q1': q1, 'q3': q3,
    }

    # 6. Worst units (top 5 from batch)
    ph = ','.join('?' * len(all_cycle_ids))
    worst_units = [dict(r) for r in query_db(
        "SELECT u.unit_number, u.block, u.floor, COUNT(d.id) as defect_count, d.raised_cycle_number "
        "FROM defect d JOIN unit_real u ON d.unit_id = u.id "
        "WHERE d.tenant_id = ? AND d.status = 'open' "
        "AND d.unit_id IN (SELECT unit_id FROM batch_unit WHERE batch_id = ? AND removed_at IS NULL AND tenant_id = ?) "
        "AND d.raised_cycle_id IN ({}) "
        "AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id "
        "AND i2.cycle_id = d.raised_cycle_id "
        "AND i2.status IN ('reviewed','approved','certified','pending_followup')) "
        "GROUP BY u.id ORDER BY defect_count DESC".format(ph),
        [tenant_id, batch_id, tenant_id] + all_cycle_ids)]
    worst_sum = sum(u['defect_count'] for u in worst_units)
    worst_pct = round(worst_sum / batch_total_defects * 100) if batch_total_defects > 0 else 0
    worst_blocks = {}
    for u in worst_units:
        key = u['block'] + ' ' + FLOOR_LABELS.get(u['floor'], 'Floor ' + str(u['floor']))
        worst_blocks[key] = worst_blocks.get(key, 0) + 1
    worst_dominant = max(worst_blocks.items(), key=lambda x: x[1]) if worst_blocks else ('', 0)

    # 7. Area breakdown
    ph = ','.join('?' * len(all_cycle_ids))
    area_raw = query_db(
        "SELECT at2.area_name AS area, COUNT(d.id) AS defect_count "
        "FROM defect d "
        "JOIN item_template it ON d.item_template_id = it.id "
        "JOIN category_template ct ON it.category_id = ct.id "
        "JOIN area_template at2 ON ct.area_id = at2.id "
        "WHERE d.tenant_id = ? AND d.status = 'open' "
        "AND d.unit_id IN (SELECT unit_id FROM batch_unit WHERE batch_id = ? AND removed_at IS NULL AND tenant_id = ?) "
        "AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id "
        "AND i2.cycle_id = d.raised_cycle_id "
        "AND i2.status IN ('reviewed','approved','certified','pending_followup')) "
        "AND d.raised_cycle_id IN ({}) "
        "GROUP BY at2.area_name ORDER BY defect_count DESC".format(ph),
        [tenant_id, batch_id, tenant_id] + all_cycle_ids)
    area_data = [dict(r) for r in area_raw]
    area_max = area_data[0]['defect_count'] if area_data else 1
    area_counts_sorted = sorted([a['defect_count'] for a in area_data])
    if area_counts_sorted:
        mid = len(area_counts_sorted) // 2
        area_median = area_counts_sorted[mid] if len(area_counts_sorted) % 2 else (area_counts_sorted[mid - 1] + area_counts_sorted[mid]) / 2
    else:
        area_median = 0
    for a in area_data:
        a['pct'] = round(a['defect_count'] / batch_total_defects * 100, 1) if batch_total_defects > 0 else 0

    # 8. Area deep dive (top 2 areas)
    dd_colours = ['#C8963E', '#3D6B8E']
    area_deep_dive = []
    ph = ','.join('?' * len(all_cycle_ids))
    for idx, area_row in enumerate(area_data[:2]):
        area_name = area_row['area']
        dd_raw = [dict(r) for r in query_db(
            "SELECT d.original_comment AS description, COUNT(*) AS count "
            "FROM defect d "
            "JOIN item_template it ON d.item_template_id = it.id "
            "JOIN category_template ct ON it.category_id = ct.id "
            "JOIN area_template at2 ON ct.area_id = at2.id "
            "WHERE d.tenant_id = ? AND d.status = 'open' "
            "AND d.unit_id IN (SELECT unit_id FROM batch_unit WHERE batch_id = ? AND removed_at IS NULL AND tenant_id = ?) "
            "AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id "
            "AND i2.cycle_id = d.raised_cycle_id "
            "AND i2.status IN ('reviewed','approved','certified','pending_followup')) "
            "AND d.raised_cycle_id IN ({}) AND at2.area_name = ? "
            "GROUP BY d.original_comment ORDER BY count DESC LIMIT 3".format(ph),
            [tenant_id, batch_id, tenant_id] + all_cycle_ids + [area_name])]
        max_dd = dd_raw[0]['count'] if dd_raw else 1
        for d in dd_raw:
            d['bar_pct'] = round(d['count'] / max_dd * 100)
        area_pct = round(area_row['defect_count'] / batch_total_defects * 100, 1) if batch_total_defects > 0 else 0
        area_deep_dive.append({
            'area': area_name, 'total': area_row['defect_count'],
            'pct': area_pct, 'colour': dd_colours[idx], 'defects': dd_raw,
        })
    dd_callout = ''
    if area_deep_dive and area_deep_dive[0]['defects']:
        a1 = area_deep_dive[0]
        d1 = a1['defects'][0]
        dd_callout = 'The most frequent defect in {} is {} ({} occurrences).'.format(
            a1['area'].title(), d1['description'].lower(), d1['count'])
        if len(area_deep_dive) >= 2 and area_deep_dive[1]['defects']:
            a2 = area_deep_dive[1]
            d2 = a2['defects'][0]
            dd_callout += ' In {}, {} leads with {} occurrences.'.format(
                a2['area'].title(), d2['description'].lower(), d2['count'])

    # 9. Recurring defects (2+ units within batch)
    ph = ','.join('?' * len(all_cycle_ids))
    recurring_raw = query_db(
        "SELECT d.original_comment, COUNT(d.id) AS cnt, COUNT(DISTINCT d.unit_id) AS unit_count "
        "FROM defect d JOIN unit_real u ON d.unit_id = u.id "
        "WHERE d.tenant_id = ? AND d.status = 'open' "
        "AND d.unit_id IN (SELECT unit_id FROM batch_unit WHERE batch_id = ? AND removed_at IS NULL AND tenant_id = ?) "
        "AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id "
        "AND i2.cycle_id = d.raised_cycle_id "
        "AND i2.status IN ('reviewed','approved','certified','pending_followup')) "
        "AND d.raised_cycle_id IN ({}) "
        "GROUP BY d.original_comment HAVING unit_count >= 2 ORDER BY cnt DESC LIMIT 10".format(ph),
        [tenant_id, batch_id, tenant_id] + all_cycle_ids)
    recurring = [dict(r) for r in recurring_raw]
    if recurring:
        top_comments = [r['original_comment'] for r in recurring]
        cat_ph = ','.join('?' * len(top_comments))
        batch_ph = ','.join('?' * len(all_cycle_ids))
        cat_raw = query_db(
            "SELECT d.original_comment, ct.category_name, COUNT(d.id) AS cat_cnt "
            "FROM defect d "
            "JOIN item_template it ON d.item_template_id = it.id "
            "JOIN category_template ct ON it.category_id = ct.id "
            "WHERE d.tenant_id = ? AND d.status = 'open' "
            "AND d.unit_id IN (SELECT unit_id FROM batch_unit WHERE batch_id = ? AND removed_at IS NULL AND tenant_id = ?) "
            "AND d.raised_cycle_id IN ({}) "
            "AND d.original_comment IN ({}) "
            "AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id "
            "AND i2.cycle_id = d.raised_cycle_id "
            "AND i2.status IN ('reviewed','approved','certified','pending_followup')) "
            "GROUP BY d.original_comment, ct.category_name "
            "ORDER BY d.original_comment, cat_cnt DESC".format(batch_ph, cat_ph),
            [tenant_id, batch_id, tenant_id] + all_cycle_ids + top_comments)
        from collections import defaultdict as _dd
        cat_map = _dd(list)
        for row in cat_raw:
            cat_map[row['original_comment']].append({'cat': row['category_name'], 'cnt': row['cat_cnt']})
        for r in recurring:
            r['cat_breakdown'] = cat_map.get(r['original_comment'], [])

    # 10. Category (trade) breakdown
    ph = ','.join('?' * len(all_cycle_ids))
    category_data = [dict(r) for r in query_db(
        "SELECT ct.category_name AS category, COUNT(d.id) AS count "
        "FROM defect d "
        "JOIN item_template it ON d.item_template_id = it.id "
        "JOIN category_template ct ON it.category_id = ct.id "
        "WHERE d.tenant_id = ? AND d.status = 'open' "
        "AND d.unit_id IN (SELECT unit_id FROM batch_unit WHERE batch_id = ? AND removed_at IS NULL AND tenant_id = ?) "
        "AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id "
        "AND i2.cycle_id = d.raised_cycle_id "
        "AND i2.status IN ('reviewed','approved','certified','pending_followup')) "
        "AND d.raised_cycle_id IN ({}) "
        "GROUP BY ct.category_name ORDER BY count DESC".format(ph),
        [tenant_id, batch_id, tenant_id] + all_cycle_ids)]
    cat_max = category_data[0]['count'] if category_data else 1
    cat_counts = sorted([c['count'] for c in category_data])
    if cat_counts:
        mid = len(cat_counts) // 2
        cat_median = cat_counts[mid] if len(cat_counts) % 2 else (cat_counts[mid - 1] + cat_counts[mid]) / 2
    else:
        cat_median = 0

    # 11. Batch rectification aggregate
    batch_rectification = None
    rect_zones = [z for z in zones if z['rectification']]
    if rect_zones:
        agg = {'r1_raised': 0, 'cleared': 0, 'new': 0, 'still_open': 0, 'zone_units': 0}
        for z in rect_zones:
            r = z['rectification']
            agg['r1_raised'] += r['r1_raised']
            agg['cleared'] += r['cleared']
            agg['new'] += r['new']
            agg['still_open'] += r['still_open']
            agg['zone_units'] += r['zone_units']
        agg['clearance_pct'] = round(agg['cleared'] / agg['r1_raised'] * 100) if agg['r1_raised'] > 0 else 0
        batch_rectification = agg

    # 12. Logo + signature
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

    area_colours = ['#C8963E', '#3D6B8E', '#4A7C59', '#C44D3F', '#7B6B8D', '#5A8A7A', '#B07D4B']
    report_date = __import__('datetime').datetime.utcnow().strftime('%d %B %Y')
    report_date_slug = __import__('datetime').datetime.utcnow().strftime('%Y%m%d')

    # === MIXED BATCH SPLIT (C1/C2) ===
    c1_zones = [z for z in zones if z['cycle_number'] == 1]
    c2_zones = [z for z in zones if z['cycle_number'] > 1]
    is_mixed = bool(c1_zones) and bool(c2_zones)

    # C1-scoped KPIs
    c1_inspected = sum(z['inspected'] for z in c1_zones)
    c1_defects = sum(z['defects'] for z in c1_zones)
    c1_avg = round(c1_defects / c1_inspected, 1) if c1_inspected > 0 else 0
    c1_items = ITEMS_PER_UNIT * c1_inspected
    c1_defect_rate = round(c1_defects / c1_items * 100, 1) if c1_items > 0 else 0
    c1_kpis = {
        'inspected': c1_inspected,
        'total_units': sum(z['total_units'] for z in c1_zones),
        'total_defects': c1_defects,
        'avg_defects': c1_avg,
        'defect_rate': c1_defect_rate,
        'items_inspected': c1_items,
        'project_avg': project_avg,
        'proj_defect_rate': proj_defect_rate,
    }

    # C1-scoped area/trade/worst — defaults to combined; re-scoped when mixed
    c1_area_data = area_data
    c1_category_data = category_data
    c1_worst_units = worst_units
    c1_area_deep_dive = area_deep_dive
    c1_dd_callout = dd_callout
    c1_recurring = recurring
    c1_area_max = area_max
    c1_area_median = area_median
    c1_cat_max = cat_max
    c1_cat_median = cat_median
    c1_worst_pct = worst_pct

    if is_mixed:
        c1_cids = [z['cycle_id'] for z in c1_zones]
        c1ph = ','.join('?' * len(c1_cids))

        c1_area_data = [dict(r) for r in query_db(
            "SELECT at2.area_name AS area, COUNT(d.id) AS defect_count "
            "FROM defect d "
            "JOIN item_template it ON d.item_template_id = it.id "
            "JOIN category_template ct ON it.category_id = ct.id "
            "JOIN area_template at2 ON ct.area_id = at2.id "
            "WHERE d.tenant_id = ? AND d.status = 'open' "
            "AND d.unit_id IN (SELECT unit_id FROM batch_unit WHERE batch_id = ? AND removed_at IS NULL AND tenant_id = ?) "
            "AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id "
            "AND i2.cycle_id = d.raised_cycle_id "
            "AND i2.status IN ('reviewed','approved','certified','pending_followup')) "
            "AND d.raised_cycle_id IN ({}) "
            "GROUP BY at2.area_name ORDER BY defect_count DESC".format(c1ph),
            [tenant_id, batch_id, tenant_id] + c1_cids)]
        c1_area_max = c1_area_data[0]['defect_count'] if c1_area_data else 1
        c1_ac = sorted([a['defect_count'] for a in c1_area_data])
        if c1_ac:
            mid = len(c1_ac) // 2
            c1_area_median = c1_ac[mid] if len(c1_ac) % 2 else (c1_ac[mid-1] + c1_ac[mid]) / 2
        else:
            c1_area_median = 0
        for a in c1_area_data:
            a['pct'] = round(a['defect_count'] / c1_defects * 100, 1) if c1_defects > 0 else 0

        c1_category_data = [dict(r) for r in query_db(
            "SELECT ct.category_name AS category, COUNT(d.id) AS count "
            "FROM defect d "
            "JOIN item_template it ON d.item_template_id = it.id "
            "JOIN category_template ct ON it.category_id = ct.id "
            "WHERE d.tenant_id = ? AND d.status = 'open' "
            "AND d.unit_id IN (SELECT unit_id FROM batch_unit WHERE batch_id = ? AND removed_at IS NULL AND tenant_id = ?) "
            "AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id "
            "AND i2.cycle_id = d.raised_cycle_id "
            "AND i2.status IN ('reviewed','approved','certified','pending_followup')) "
            "AND d.raised_cycle_id IN ({}) "
            "GROUP BY ct.category_name ORDER BY count DESC".format(c1ph),
            [tenant_id, batch_id, tenant_id] + c1_cids)]
        c1_cat_max = c1_category_data[0]['count'] if c1_category_data else 1
        c1_cc = sorted([c['count'] for c in c1_category_data])
        if c1_cc:
            mid = len(c1_cc) // 2
            c1_cat_median = c1_cc[mid] if len(c1_cc) % 2 else (c1_cc[mid-1] + c1_cc[mid]) / 2
        else:
            c1_cat_median = 0

        c1_worst_units = [dict(r) for r in query_db(
            "SELECT u.unit_number, u.block, u.floor, COUNT(d.id) as defect_count "
            "FROM defect d JOIN unit_real u ON d.unit_id = u.id "
            "WHERE d.tenant_id = ? AND d.status = 'open' "
            "AND d.unit_id IN (SELECT unit_id FROM batch_unit WHERE batch_id = ? AND removed_at IS NULL AND tenant_id = ?) "
            "AND d.raised_cycle_id IN ({}) "
            "AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id "
            "AND i2.cycle_id = d.raised_cycle_id "
            "AND i2.status IN ('reviewed','approved','certified','pending_followup')) "
            "GROUP BY u.id ORDER BY defect_count DESC".format(c1ph),
            [tenant_id, batch_id, tenant_id] + c1_cids)]
        c1_ws = sum(u['defect_count'] for u in c1_worst_units)
        c1_worst_pct = round(c1_ws / c1_defects * 100) if c1_defects > 0 else 0

        c1_area_deep_dive = []
        for idx2, ar2 in enumerate(c1_area_data[:2]):
            aname = ar2['area']
            dd2 = [dict(r) for r in query_db(
                "SELECT d.original_comment AS description, COUNT(*) AS count "
                "FROM defect d "
                "JOIN item_template it ON d.item_template_id = it.id "
                "JOIN category_template ct ON it.category_id = ct.id "
                "JOIN area_template at2 ON ct.area_id = at2.id "
                "WHERE d.tenant_id = ? AND d.status = 'open' "
                "AND d.unit_id IN (SELECT unit_id FROM batch_unit WHERE batch_id = ? AND removed_at IS NULL AND tenant_id = ?) "
                "AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id "
                "AND i2.cycle_id = d.raised_cycle_id "
                "AND i2.status IN ('reviewed','approved','certified','pending_followup')) "
                "AND d.raised_cycle_id IN ({}) AND at2.area_name = ? "
                "GROUP BY d.original_comment ORDER BY count DESC LIMIT 3".format(c1ph),
                [tenant_id, batch_id, tenant_id] + c1_cids + [aname])]
            mx = dd2[0]['count'] if dd2 else 1
            for d in dd2:
                d['bar_pct'] = round(d['count'] / mx * 100)
            apct = round(ar2['defect_count'] / c1_defects * 100, 1) if c1_defects > 0 else 0
            c1_area_deep_dive.append({
                'area': aname, 'total': ar2['defect_count'],
                'pct': apct, 'colour': dd_colours[idx2], 'defects': dd2,
            })
        c1_dd_callout = ''
        if c1_area_deep_dive and c1_area_deep_dive[0]['defects']:
            a1c = c1_area_deep_dive[0]
            d1c = a1c['defects'][0]
            c1_dd_callout = 'The most frequent defect in {} is {} ({} occurrences).'.format(
                a1c['area'].title(), d1c['description'].lower(), d1c['count'])

        c1_recurring = [dict(r) for r in query_db(
            "SELECT d.original_comment, COUNT(d.id) AS cnt, COUNT(DISTINCT d.unit_id) AS unit_count "
            "FROM defect d JOIN unit_real u ON d.unit_id = u.id "
            "WHERE d.tenant_id = ? AND d.status = 'open' "
            "AND d.unit_id IN (SELECT unit_id FROM batch_unit WHERE batch_id = ? AND removed_at IS NULL AND tenant_id = ?) "
            "AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id "
            "AND i2.cycle_id = d.raised_cycle_id "
            "AND i2.status IN ('reviewed','approved','certified','pending_followup')) "
            "AND d.raised_cycle_id IN ({}) "
            "GROUP BY d.original_comment HAVING unit_count >= 2 ORDER BY cnt DESC LIMIT 10".format(c1ph),
            [tenant_id, batch_id, tenant_id] + c1_cids)]

    # C2 unit rectification table
    c2_unit_table = []
    c2_total_r1 = 0
    c2_total_cleared = 0
    c2_total_new = 0
    c2_total_still_open = 0
    for z in c2_zones:
        cyc_id = z['cycle_id']
        prev_row = query_db(
            "SELECT id FROM inspection_cycle WHERE block=? AND floor=? AND cycle_number=? AND tenant_id=?",
            [z['block'], z['floor'], z['cycle_number'] - 1, tenant_id], one=True)
        if not prev_row:
            continue
        prev_id = prev_row['id']
        for u in z['units']:
            if u['insp_status'] not in reviewed_statuses:
                continue
            uid = u['unit_id']
            r1r = query_db('SELECT COUNT(*) as cnt FROM defect WHERE raised_cycle_id=? AND unit_id=? AND tenant_id=?',
                           [prev_id, uid, tenant_id], one=True)
            clr = query_db('SELECT COUNT(*) as cnt FROM defect WHERE cleared_cycle_id=? AND unit_id=? AND tenant_id=?',
                           [cyc_id, uid, tenant_id], one=True)
            nwr = query_db('SELECT COUNT(*) as cnt FROM defect WHERE raised_cycle_id=? AND unit_id=? AND tenant_id=?',
                           [cyc_id, uid, tenant_id], one=True)
            r1c = r1r['cnt'] if r1r else 0
            clc = clr['cnt'] if clr else 0
            nwc = nwr['cnt'] if nwr else 0
            so = max(r1c - clc, 0)
            cpct = round(clc / r1c * 100) if r1c > 0 else 0
            c2_unit_table.append({
                'unit_number': u['unit_number'],
                'zone': '{} {}'.format(z['block'], z['floor_label']),
                'cycle_number': z['cycle_number'],
                'r1_defects': r1c, 'cleared': clc,
                'still_open': so, 'new': nwc, 'clearance_pct': cpct,
            })
            c2_total_r1 += r1c
            c2_total_cleared += clc
            c2_total_new += nwc
            c2_total_still_open += so
    c2_unit_table.sort(key=lambda x: (-x['cycle_number'], x['clearance_pct'], -x['still_open']))
    c2_summary = {
        'total_r1': c2_total_r1, 'total_cleared': c2_total_cleared,
        'total_new': c2_total_new, 'total_still_open': c2_total_still_open,
        'clearance_pct': round(c2_total_cleared / c2_total_r1 * 100) if c2_total_r1 > 0 else 0,
        'units_inspected': len(c2_unit_table),
    }

    # C2 area/trade (remaining open defects for C2 units)
    c2_area_data = []
    c2_trade_data = []
    c2_area_max = 1
    c2_trade_max = 1
    if c2_zones:
        c2_uids = []
        for z in c2_zones:
            for u in z['units']:
                if u['insp_status'] in reviewed_statuses:
                    c2_uids.append(u['unit_id'])
        if c2_uids:
            uph2 = ','.join('?' * len(c2_uids))
            c2_area_data = [dict(r) for r in query_db(
                "SELECT at2.area_name AS area, COUNT(d.id) AS defect_count "
                "FROM defect d "
                "JOIN item_template it ON d.item_template_id = it.id "
                "JOIN category_template ct ON it.category_id = ct.id "
                "JOIN area_template at2 ON ct.area_id = at2.id "
                "WHERE d.tenant_id = ? AND d.status = 'open' AND d.unit_id IN ({}) "
                "GROUP BY at2.area_name ORDER BY defect_count DESC".format(uph2),
                [tenant_id] + c2_uids)]
            c2_area_max = c2_area_data[0]['defect_count'] if c2_area_data else 1
            c2_trade_data = [dict(r) for r in query_db(
                "SELECT ct.category_name AS category, COUNT(d.id) AS count "
                "FROM defect d "
                "JOIN item_template it ON d.item_template_id = it.id "
                "JOIN category_template ct ON it.category_id = ct.id "
                "WHERE d.tenant_id = ? AND d.status = 'open' AND d.unit_id IN ({}) "
                "GROUP BY ct.category_name ORDER BY count DESC".format(uph2),
                [tenant_id] + c2_uids)]
            c2_trade_max = c2_trade_data[0]['count'] if c2_trade_data else 1

    return {
        'batch': batch,
        'zones': zones,
        'kpis': kpis,
        'area_data': area_data,
        'area_max': area_max,
        'area_median': area_median,
        'area_colours': area_colours,
        'area_deep_dive': area_deep_dive,
        'dd_callout': dd_callout,
        'recurring': recurring,
        'category_data': category_data,
        'cat_max': cat_max,
        'cat_median': cat_median,
        'worst_units': worst_units,
        'worst_pct': worst_pct,
        'worst_dominant_zone': worst_dominant[0],
        'worst_dominant_count': worst_dominant[1],
        'batch_rectification': batch_rectification,
        'logo_b64': logo_b64,
        'sig_b64': sig_b64,
        'report_date': report_date,
        'report_date_slug': report_date_slug,
        'floor_labels': FLOOR_LABELS,
        'batch_id': batch_id,
        'is_mixed': is_mixed,
        'c1_zones': c1_zones,
        'c2_zones': c2_zones,
        'c1_kpis': c1_kpis,
        'c1_area_data': c1_area_data,
        'c1_category_data': c1_category_data,
        'c1_worst_units': c1_worst_units,
        'c1_worst_pct': c1_worst_pct,
        'c1_area_deep_dive': c1_area_deep_dive,
        'c1_dd_callout': c1_dd_callout,
        'c1_recurring': c1_recurring,
        'c1_area_max': c1_area_max,
        'c1_area_median': c1_area_median,
        'c1_cat_max': c1_cat_max,
        'c1_cat_median': c1_cat_median,
        'c2_unit_table': c2_unit_table,
        'c2_summary': c2_summary,
        'c2_area_data': c2_area_data,
        'c2_trade_data': c2_trade_data,
        'c2_area_max': c2_area_max,
        'c2_trade_max': c2_trade_max,
    }


@analytics_bp.route('/inspector/<inspector_name>')
@require_manager
def inspector_detail(inspector_name):
    tenant_id = session.get('tenant_id', 'MONOGRAPH')
    FLOOR_LABELS = {0: 'Ground', 1: '1st Floor', 2: '2nd Floor'}

    # Get all units this inspector inspected with zone info
    units = [dict(r) for r in query_db("""
        SELECT i.inspector_name, u.id as unit_id, u.unit_number, u.block, u.floor,
            i.id as inspection_id, i.cycle_id, i.status as insp_status,
            i.cycle_number as round_number,
            COUNT(d.id) as defect_count
        FROM inspection i
        JOIN unit_real u ON i.unit_id = u.id
        LEFT JOIN defect d ON d.unit_id = u.id AND d.raised_cycle_id = i.cycle_id
            AND d.status = 'open' AND d.tenant_id = u.tenant_id
        WHERE i.tenant_id = ? AND i.inspector_name = ?
            AND i.status IN ('reviewed','approved','certified','pending_followup')
            AND u.unit_number NOT LIKE 'TEST%'
        GROUP BY u.unit_number, i.cycle_id
        ORDER BY defect_count DESC
    """, [tenant_id, inspector_name])]

    if not units:
        return render_template('analytics/inspector_detail.html',
                               inspector_name=inspector_name, has_data=False,
                               units=[], zone_score=0, total_defects=0,
                               total_units=0, raw_avg=0, colour='#6B6B6B')

    # Zone averages
    zone_avgs = {}
    zone_data = [dict(r) for r in query_db("""
        SELECT u.block, u.floor,
            ROUND(COUNT(d.id) * 1.0 / NULLIF(COUNT(DISTINCT u.id), 0), 1) as avg_defects
        FROM unit_real u
        LEFT JOIN inspection i ON i.unit_id = u.id AND i.tenant_id = u.tenant_id
            AND i.status IN ('reviewed','approved','certified','pending_followup')
        LEFT JOIN defect d ON d.unit_id = u.id AND d.status = 'open' AND d.tenant_id = u.tenant_id
        WHERE u.tenant_id = ? AND u.unit_number NOT LIKE 'TEST%'
        GROUP BY u.block, u.floor
        HAVING COUNT(DISTINCT CASE WHEN i.id IS NOT NULL THEN u.id END) > 0
    """, [tenant_id])]
    for z in zone_data:
        zone_avgs[(z['block'], z['floor'])] = z['avg_defects']

    # Enrich units
    variances = []
    total_defects = 0
    for u in units:
        zone_avg = zone_avgs.get((u['block'], u['floor']), 0)
        u['zone_avg'] = zone_avg
        u['variance'] = round((u['defect_count'] - zone_avg) / zone_avg * 100, 1) if zone_avg > 0 else 0
        u['floor_label'] = FLOOR_LABELS.get(u['floor'], 'Floor ' + str(u['floor']))
        u['var_colour'] = '#4A7C59' if u['variance'] >= 0 else '#C44D3F'
        variances.append(u['variance'])
        total_defects += u['defect_count']

    total_units = len(units)
    raw_avg = round(total_defects / total_units, 1) if total_units > 0 else 0
    zone_score = round(sum(variances) / len(variances), 1) if variances else 0
    colour = '#C44D3F' if abs(zone_score) > 30 else '#C8963E' if abs(zone_score) > 15 else '#4A7C59'

    return render_template('analytics/inspector_detail.html',
                           inspector_name=inspector_name, has_data=True,
                           units=units, zone_score=zone_score,
                           total_defects=total_defects, total_units=total_units,
                           raw_avg=raw_avg, colour=colour)


def _build_audit_data_dict():
    """Shared data builder for inspector audit trail.

    Returns split C1 (snag) and C2+ (desnag) data structures.
    Groups by inspector_id (stable identity), resolves display name via
    LEFT JOIN to inspector table (single source of truth for names).
    Orphan inspector_ids render as "Unknown (<id>)" so data issues stay visible.
    """
    tenant_id = session['tenant_id']
    from_date = request.args.get('from_date', '')
    to_date = request.args.get('to_date', '')

    # Build date filter
    date_filter = ''
    params = [tenant_id]
    if from_date:
        date_filter += ' AND i.inspection_date >= ?'
        params.append(from_date)
    if to_date:
        date_filter += ' AND i.inspection_date <= ?'
        params.append(to_date)

    # Fetch ALL inspections (C1 + C2+) in one query, with resolved inspector display name.
    # Role gate: only inspector/team_lead roles OR orphan IDs (insp.id IS NULL).
    # This excludes admins/managers that might appear on inspection rows by accident.
    rows = [dict(r) for r in query_db("""
        SELECT i.inspector_id,
               COALESCE(insp.name, 'Unknown (' || i.inspector_id || ')') AS inspector_display,
               i.inspection_date, i.started_at, i.submitted_at,
               i.paused_at, i.total_paused_seconds,
               i.status AS insp_status, i.id AS inspection_id, i.cycle_number,
               u.id AS unit_id, u.unit_number, u.block, u.floor,
               COUNT(d.id) AS defect_count
        FROM inspection i
        JOIN unit_real u ON i.unit_id = u.id
        LEFT JOIN inspector insp ON insp.id = i.inspector_id
        LEFT JOIN defect d ON d.unit_id = u.id
            AND d.tenant_id = u.tenant_id
            AND (
                (i.cycle_number = 1 AND d.raised_cycle_id = i.cycle_id)
                OR
                (i.cycle_number > 1 AND d.addressed_cycle_number = i.cycle_number)
            )
        WHERE i.tenant_id = ?
          AND i.status IN ('reviewed','approved','certified','pending_followup')
          AND i.inspector_id IS NOT NULL
          AND u.unit_number NOT LIKE 'TEST%%'
          AND (insp.role IN ('inspector','team_lead') OR insp.id IS NULL)
          {date_filter}
        GROUP BY i.id
        ORDER BY inspector_display, i.inspection_date DESC, u.unit_number
    """.format(date_filter=date_filter), params)]

    floor_labels = {0: 'Ground', 1: '1st Floor', 2: '2nd Floor', 3: '3rd Floor'}
    status_map = {
        'in_progress': ('In Progress', '#FEF3C7', '#92400E'),
        'submitted': ('Submitted', '#DBEAFE', '#1E40AF'),
        'reviewed': ('Reviewed', '#D1FAE5', '#065F46'),
        'pending_followup': ('Signed Off', '#E5E7EB', '#374151'),
        'approved': ('Approved', '#D1FAE5', '#065F46'),
        'certified': ('Certified', '#D1FAE5', '#065F46'),
    }

    def calc_duration(started, submitted, total_paused_seconds=0, paused_at=None):
        if not started:
            return 'N/A'
        effective_end = paused_at if paused_at else submitted
        if not effective_end:
            return 'N/A'
        submitted = effective_end
        try:
            from datetime import datetime
            for fmt in ('%Y-%m-%dT%H:%M:%S.%f%z', '%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S'):
                try:
                    s = datetime.strptime(started.replace('+00:00', '').replace('Z', ''), fmt.replace('%z', ''))
                    break
                except ValueError:
                    s = None
            for fmt in ('%Y-%m-%dT%H:%M:%S.%f%z', '%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S'):
                try:
                    e = datetime.strptime(submitted.replace('+00:00', '').replace('Z', ''), fmt.replace('%z', ''))
                    break
                except ValueError:
                    e = None
            if not s or not e:
                return 'N/A'
            diff = e - s
            total_secs = diff.total_seconds() - (total_paused_seconds or 0)
            if total_secs < 0:
                total_secs = 0
            total_mins = int(total_secs / 60)
            if total_mins < 2:
                return 'N/A'
            if total_mins < 60:
                return f'{total_mins}m'
            hours = total_mins // 60
            mins = total_mins % 60
            return f'{hours}h {mins}m'
        except Exception:
            return 'N/A'

    from collections import OrderedDict, defaultdict

    groups = OrderedDict()
    for r in rows:
        iid = r['inspector_id']
        if iid not in groups:
            groups[iid] = {
                'inspector_id': iid,
                'name': r['inspector_display'],
                'snag': [],
                'desnag': [],
            }
        zone = '{} {}'.format(r['block'], floor_labels.get(r['floor'], 'Floor ' + str(r['floor'])))
        status_info = status_map.get(r['insp_status'], ('Unknown', '#F3F4F6', '#6B7280'))
        duration = calc_duration(r['started_at'], r['submitted_at'], r['total_paused_seconds'], r['paused_at'])
        entry = {
            'unit_id': r['unit_id'],
            'unit_number': r['unit_number'],
            'zone': zone,
            'inspection_date': r['inspection_date'] or 'N/A',
            'cycle': 'C{}'.format(r['cycle_number']),
            'cycle_number': r['cycle_number'],
            'duration': duration,
            'defect_count': r['defect_count'],
            'status_label': status_info[0],
            'status_bg': status_info[1],
            'status_colour': status_info[2],
        }
        if r['cycle_number'] == 1:
            groups[iid]['snag'].append(entry)
        else:
            groups[iid]['desnag'].append(entry)

    colours = ['#C8963E', '#3D6B8E', '#4A7C59', '#C44D3F', '#7B6B8D', '#5A8A7A', '#B07D4B']

    def avg_dur_label(units):
        durs = [u['duration'] for u in units if u['duration'] != 'N/A']
        if not durs:
            return None
        total_mins = 0
        count = 0
        for d in durs:
            if 'h' in d:
                parts = d.replace('h', '').replace('m', '').split()
                total_mins += int(parts[0]) * 60 + (int(parts[1]) if len(parts) > 1 else 0)
            elif 'm' in d:
                total_mins += int(d.replace('m', ''))
            count += 1
        if not count:
            return None
        am = total_mins // count
        return f'{am // 60}h {am % 60}m' if am >= 60 else f'{am}m'

    def date_range_label(units):
        dates = [u['inspection_date'] for u in units if u['inspection_date'] != 'N/A']
        if not dates:
            return ''
        s = sorted(dates)
        return s[0] if s[0] == s[-1] else f'{s[0]} to {s[-1]}'

    detail_groups = []
    for i, (iid, g) in enumerate(groups.items()):
        colour = colours[i % len(colours)]
        snag_units = g['snag']
        desnag_units = g['desnag']
        detail_groups.append({
            'inspector_id': iid,
            'name': g['name'],
            'colour': colour,
            'snag': {
                'units': snag_units,
                'unit_count': len(snag_units),
                'total_defects': sum(u['defect_count'] for u in snag_units),
                'avg_duration': avg_dur_label(snag_units),
                'date_range': date_range_label(snag_units),
            },
            'desnag': {
                'units': desnag_units,
                'unit_count': len(desnag_units),
                'total_defects': sum(u['defect_count'] for u in desnag_units),
                'avg_duration': avg_dur_label(desnag_units),
                'date_range': date_range_label(desnag_units),
            },
        })

    # Sort detail_groups by total units descending (payroll-heaviest first).
    detail_groups.sort(key=lambda g: g['snag']['unit_count'] + g['desnag']['unit_count'], reverse=True)

    snag_total_units = sum(g['snag']['unit_count'] for g in detail_groups)
    snag_total_defects = sum(g['snag']['total_defects'] for g in detail_groups)
    snag_inspector_count = sum(1 for g in detail_groups if g['snag']['unit_count'] > 0)
    desnag_total_units = sum(g['desnag']['unit_count'] for g in detail_groups)
    desnag_total_defects = sum(g['desnag']['total_defects'] for g in detail_groups)
    desnag_inspector_count = sum(1 for g in detail_groups if g['desnag']['unit_count'] > 0)

    # C1 zone-adjusted scoring
    zone_cards = [dict(r) for r in query_db("""
        SELECT u.block, u.floor,
            COUNT(DISTINCT u.id) as inspected,
            ROUND(1.0 * COUNT(d.id) / COUNT(DISTINCT u.id), 1) as avg_defects
        FROM inspection i
        JOIN unit_real u ON i.unit_id = u.id
        LEFT JOIN defect d ON d.unit_id = u.id AND d.raised_cycle_id = i.cycle_id
            AND d.tenant_id = u.tenant_id
        WHERE i.tenant_id = ? AND i.cycle_number = 1
            AND i.status IN ('reviewed','approved','certified','pending_followup')
            AND u.unit_number NOT LIKE 'TEST%'
        GROUP BY u.block, u.floor
        HAVING inspected > 0
    """, [tenant_id])]
    zone_avgs = {(c['block'], c['floor']): c['avg_defects'] for c in zone_cards}

    inspector_raw = [dict(r) for r in query_db("""
        SELECT i.inspector_id,
            COALESCE(insp.name, 'Unknown (' || i.inspector_id || ')') AS inspector_display,
            u.unit_number, u.block, u.floor,
            COUNT(d.id) as defect_count
        FROM inspection i
        JOIN unit_real u ON i.unit_id = u.id
        LEFT JOIN inspector insp ON insp.id = i.inspector_id
        LEFT JOIN defect d ON d.unit_id = u.id AND d.raised_cycle_id = i.cycle_id
            AND d.tenant_id = u.tenant_id
        WHERE i.tenant_id = ? AND i.cycle_number = 1
            AND i.status IN ('reviewed','approved','certified','pending_followup')
            AND i.inspector_id IS NOT NULL
            AND u.unit_number NOT LIKE 'TEST%'
            AND (insp.role IN ('inspector','team_lead') OR insp.id IS NULL)
        GROUP BY i.inspector_id, u.unit_number, u.block, u.floor
        ORDER BY inspector_display
    """, [tenant_id])]

    import statistics as _stats
    insp_data = defaultdict(lambda: {'name': '', 'units': 0, 'total_defects': 0, 'variances': []})
    for r in inspector_raw:
        iid = r['inspector_id']
        zone_avg = zone_avgs.get((r['block'], r['floor']), 0)
        variance_pct = round((r['defect_count'] - zone_avg) / zone_avg * 100, 1) if zone_avg > 0 else 0
        insp_data[iid]['name'] = r['inspector_display']
        insp_data[iid]['units'] += 1
        insp_data[iid]['total_defects'] += r['defect_count']
        insp_data[iid]['variances'].append(variance_pct)

    snag_cards = []
    for iid, d in insp_data.items():
        avg_variance = round(sum(d['variances']) / len(d['variances']), 1) if d['variances'] else 0
        consistency = round(_stats.stdev(d['variances']), 1) if len(d['variances']) > 1 else 0
        raw_avg = round(d['total_defects'] / d['units'], 1) if d['units'] > 0 else 0
        snag_cards.append({
            'inspector_id': iid,
            'name': d['name'],
            'units': d['units'],
            'total_defects': d['total_defects'],
            'raw_avg': raw_avg,
            'zone_score': avg_variance,
            'consistency': consistency,
            'colour': '#C44D3F' if abs(avg_variance) > 30 else '#C8963E' if abs(avg_variance) > 15 else '#4A7C59',
        })
    snag_cards.sort(key=lambda x: x['zone_score'], reverse=True)

    desnag_cards = []
    for g in detail_groups:
        if g['desnag']['unit_count'] == 0:
            continue
        units = g['desnag']['unit_count']
        defects = g['desnag']['total_defects']
        desnag_cards.append({
            'inspector_id': g['inspector_id'],
            'name': g['name'],
            'units': units,
            'total_defects': defects,
            'raw_avg': round(defects / units, 1) if units else 0,
            'colour': '#6B6B6B',
        })
    desnag_cards.sort(key=lambda x: x['units'], reverse=True)

    # --------------------------------------------------------------
    # SCRUBBER DATA: per-batch zone-adjusted variance for each inspector.
    # Uses the SAME global zone_avgs benchmark as the lifetime scoring
    # so batch scores are directly comparable to lifetime scores and
    # to each other. Only the Zone-Adjusted Ranking chart consumes this.
    # --------------------------------------------------------------
    inspector_raw_with_batch = [dict(r) for r in query_db('''
        SELECT i.inspector_id,
            COALESCE(insp.name, 'Unknown (' || i.inspector_id || ')') AS inspector_display,
            u.block, u.floor,
            COUNT(d.id) as defect_count,
            ib.name AS batch_name,
            ib.status AS batch_status
        FROM inspection i
        JOIN unit_real u ON i.unit_id = u.id
        JOIN batch_unit bu ON bu.unit_id = i.unit_id
            AND bu.cycle_id = i.cycle_id
            AND bu.tenant_id = i.tenant_id
        JOIN inspection_batch ib ON ib.id = bu.batch_id
        LEFT JOIN inspector insp ON insp.id = i.inspector_id
        LEFT JOIN defect d ON d.unit_id = u.id
            AND d.raised_cycle_id = i.cycle_id
            AND d.tenant_id = u.tenant_id
        WHERE i.tenant_id = ? AND i.cycle_number = 1
            AND i.status IN ('reviewed','approved','certified','pending_followup')
            AND i.inspector_id IS NOT NULL
            AND u.unit_number NOT LIKE 'TEST%'
            AND (insp.role IN ('inspector','team_lead') OR insp.id IS NULL)
        GROUP BY i.id
        ORDER BY ib.name, inspector_display
    ''', [tenant_id])]

    # Partition by batch -> per-inspector unit list with variances against GLOBAL zone avg.
    from collections import defaultdict as _dd
    per_batch = _dd(lambda: _dd(lambda: {'name': '', 'variances': [], 'units': 0, 'total_defects': 0}))
    batch_meta = {}  # batch_name -> {status, inspections}

    for r in inspector_raw_with_batch:
        bname = r['batch_name']
        iid = r['inspector_id']
        zone_avg = zone_avgs.get((r['block'], r['floor']), 0)
        variance_pct = round((r['defect_count'] - zone_avg) / zone_avg * 100, 1) if zone_avg > 0 else 0
        per_batch[bname][iid]['name'] = r['inspector_display']
        per_batch[bname][iid]['variances'].append(variance_pct)
        per_batch[bname][iid]['units'] += 1
        per_batch[bname][iid]['total_defects'] += r['defect_count']
        if bname not in batch_meta:
            batch_meta[bname] = {'status': r['batch_status'], 'inspections': 0}
        batch_meta[bname]['inspections'] += 1

    def _parse_batch_name(bname):
        # e.g. "SR-012 10 Apr 2026" -> ("SR-012", "10 Apr 2026")
        parts = bname.split(' ', 1)
        return (parts[0], parts[1] if len(parts) > 1 else '')

    def _score_colour(v):
        av = abs(v)
        if av > 30: return '#C44D3F'
        if av > 15: return '#C8963E'
        return '#4A7C59'

    def _callout_html(inspectors_sorted, context_label):
        # inspectors_sorted is descending by zone_score. Picks top and bottom for narrative.
        if len(inspectors_sorted) < 2:
            if len(inspectors_sorted) == 1:
                i0 = inspectors_sorted[0]
                return f'<strong>{i0["name"]}</strong> was the only inspector on {context_label} ({i0["units"]} units). Variance shown against global zone averages.'
            return ''
        top = inspectors_sorted[0]
        bottom = inspectors_sorted[-1]
        top_dir = 'more' if top['zone_score'] > 0 else 'fewer'
        bottom_dir = 'more' if bottom['zone_score'] > 0 else 'fewer'
        return (f'<strong>{top["name"]}</strong> finds {abs(top["zone_score"])}% {top_dir} defects than zone averages '
                f'({top["units"]} units). <strong>{bottom["name"]}</strong> finds {abs(bottom["zone_score"])}% {bottom_dir} '
                f'({bottom["units"]} units). Consistency score measures how steady an inspector is across units &mdash; lower is more reliable.')

    # Build batches_data entries.
    batches_data = {}

    # "All time" entry = the existing lifetime snag_cards.
    all_inspectors = [
        {
            'inspector_id': c['inspector_id'],
            'name': c['name'],
            'zone_score': c['zone_score'],
            'units': c['units'],
            'raw_avg': c['raw_avg'],
            'consistency': c['consistency'],
            'colour': c['colour'],
        }
        for c in snag_cards
    ]
    batches_data['all'] = {
        'key': 'all',
        'label': 'All time',
        'short': 'All',
        'date': '',
        'status': '',
        'unit_count': snag_total_units,
        'inspections': snag_total_units,
        'inspectors': all_inspectors,
        'title': 'Zone-Adjusted Ranking \u2014 All time',
        'subtitle': 'Cumulative view across all batches. Positive = more thorough. Negative = finding fewer than expected.',
        'callout_html': _callout_html(all_inspectors, 'all batches'),
    }

    # Per-batch entries.
    for bname in sorted(per_batch.keys()):
        short, datepart = _parse_batch_name(bname)
        meta = batch_meta.get(bname, {'status': 'complete', 'inspections': 0})
        batch_inspectors = []
        for iid, d in per_batch[bname].items():
            avg_variance = round(sum(d['variances']) / len(d['variances']), 1) if d['variances'] else 0
            consistency = round(_stats.stdev(d['variances']), 1) if len(d['variances']) > 1 else 0
            raw_avg = round(d['total_defects'] / d['units'], 1) if d['units'] > 0 else 0
            batch_inspectors.append({
                'inspector_id': iid,
                'name': d['name'],
                'zone_score': avg_variance,
                'units': d['units'],
                'raw_avg': raw_avg,
                'consistency': consistency,
                'colour': _score_colour(avg_variance),
            })
        batch_inspectors.sort(key=lambda x: x['zone_score'], reverse=True)

        insp_count = len(batch_inspectors)
        if meta['status'] == 'open':
            subtitle = f'In progress \u2014 {insp_count} inspector{"s" if insp_count != 1 else ""}, {meta["inspections"]} units inspected so far. Numbers will shift as more come in.'
        else:
            single_worker_note = ''
            single_worker_count = sum(1 for x in batch_inspectors if x['units'] == 1)
            if single_worker_count > 0 and len(batch_inspectors) > 1:
                single_worker_note = f' ({single_worker_count} inspector{"s" if single_worker_count != 1 else ""} worked only one unit \u2014 variance is noisier for these.)'
            subtitle = f'{insp_count} inspector{"s" if insp_count != 1 else ""} worked this batch across {meta["inspections"]} units.{single_worker_note}'

        batches_data[bname] = {
            'key': bname,
            'label': bname,
            'short': short,
            'date': datepart,
            'status': meta['status'],
            'unit_count': meta['inspections'],
            'inspections': meta['inspections'],
            'inspectors': batch_inspectors,
            'title': f'Zone-Adjusted Ranking \u2014 {short} \u00b7 {datepart}' if datepart else f'Zone-Adjusted Ranking \u2014 {short}',
            'subtitle': subtitle,
            'callout_html': _callout_html(batch_inspectors, short),
        }

    # batches_list: ordered list of scrubber nodes. "All" first, then batches chronologically by SR number.
    batches_list = [{
        'key': 'all',
        'label': 'All time',
        'short': 'All',
        'date': '',
        'status': '',
        'unit_count': snag_total_units,
    }]
    for bname in sorted(per_batch.keys()):
        short, datepart = _parse_batch_name(bname)
        meta = batch_meta.get(bname, {'status': 'complete', 'inspections': 0})
        batches_list.append({
            'key': bname,
            'label': bname,
            'short': short,
            'date': datepart,
            'status': meta['status'],
            'unit_count': meta['inspections'],
        })

    period_label = ''
    if from_date and to_date:
        period_label = f'{from_date} to {to_date}'
    elif from_date:
        period_label = f'From {from_date}'
    elif to_date:
        period_label = f'Until {to_date}'

    return dict(
        detail_groups=detail_groups,
        snag_cards=snag_cards,
        desnag_cards=desnag_cards,
        snag_totals={'inspectors': snag_inspector_count, 'units': snag_total_units, 'defects': snag_total_defects},
        desnag_totals={'inspectors': desnag_inspector_count, 'units': desnag_total_units, 'defects': desnag_total_defects},
        batches_data=batches_data,
        batches_list=batches_list,
        from_date=from_date,
        to_date=to_date,
        period_label=period_label,
    )


@analytics_bp.route('/audit')
@require_team_lead
def inspector_audit():
    """Inspector Audit Trail - payment verification page."""
    data = _build_audit_data_dict()
    return render_template('analytics/inspector_audit.html', **data)


@analytics_bp.route('/audit/units')
@require_team_lead
def inspector_audit_units():
    """Unit-centric audit trail - who inspected what, by cycle."""
    tenant_id = session['tenant_id']
    floor_labels = {0: 'Ground', 1: '1st Floor', 2: '2nd Floor', 3: '3rd Floor'}

    rows = [dict(r) for r in query_db("""
        SELECT u.id as unit_id, u.unit_number, u.block, u.floor,
               i.cycle_number, i.inspection_date, i.inspector_name, i.status
        FROM unit_real u
        LEFT JOIN inspection i ON i.unit_id = u.id AND i.tenant_id = u.tenant_id
            AND i.status IN ('reviewed','approved','certified','pending_followup')
        WHERE u.tenant_id = ?
        ORDER BY u.block, u.floor, CAST(u.unit_number AS INTEGER), i.cycle_number
    """, [tenant_id])]

    # Build unit map: {unit_id: {unit_number, block, floor, c1: {date, inspector}, c2: {...}, c3: {...}}}
    from collections import OrderedDict
    units = OrderedDict()
    for r in rows:
        uid = r['unit_id']
        if uid not in units:
            floor_val = r['floor']
            units[uid] = {
                'unit_number': r['unit_number'],
                'block': r['block'],
                'floor': floor_val,
                'zone': '{} {}'.format(r['block'], floor_labels.get(floor_val, 'Floor ' + str(floor_val))),
                'c1_date': None, 'c1_inspector': None,
                'c2_date': None, 'c2_inspector': None,
                'c3_date': None, 'c3_inspector': None,
            }
        cn = r.get('cycle_number')
        if cn and r['inspection_date']:
            prefix = 'c{}'.format(min(cn, 3))
            units[uid][prefix + '_date'] = r['inspection_date']
            units[uid][prefix + '_inspector'] = r['inspector_name']

    # Group by zone (block + floor)
    zones = OrderedDict()
    for uid, u in units.items():
        z = u['zone']
        if z not in zones:
            zones[z] = []
        zones[z].append(u)

    return render_template('analytics/inspector_audit_units.html',
        zones=zones,
        total_units=len(units))


@analytics_bp.route('/audit/view')
@require_team_lead
def inspector_audit_view():
    """Standalone HTML view for audit trail PDF."""
    data = _build_audit_data_dict()
    from datetime import datetime as dt
    data['now'] = dt.now().strftime('%Y-%m-%d %H:%M')
    return render_template('analytics/inspector_audit_pdf.html', **data)


@analytics_bp.route('/audit/pdf')
@require_team_lead
def inspector_audit_pdf():
    """Download audit trail as PDF."""
    data = _build_audit_data_dict()
    from datetime import datetime as dt
    data['now'] = dt.now().strftime('%Y-%m-%d %H:%M')
    from app.services.pdf_playwright import html_to_pdf
    html_str = render_template('analytics/inspector_audit_pdf.html', **data)
    pdf_bytes = html_to_pdf(html_str)
    resp = make_response(pdf_bytes)
    resp.headers['Content-Type'] = 'application/pdf'
    period = data.get('period_label', '').replace(' ', '_') or 'all'
    resp.headers['Content-Disposition'] = f'attachment; filename=inspector_audit_{period}.pdf'
    return resp


@analytics_bp.route('/login-status')
@require_manager
def login_status():
    """Admin view: inspector login status."""
    tenant_id = session['tenant_id']
    inspectors = [dict(r) for r in query_db("""
        SELECT id, name, email, role, last_login, active
        FROM inspector
        WHERE tenant_id = ? AND active = 1
        ORDER BY last_login DESC NULLS LAST, name
    """, [tenant_id])]

    floor_labels = {0: 'Ground', 1: '1st Floor', 2: '2nd Floor'}

    for insp in inspectors:
        # Get assigned units from latest batch
        units = [dict(r) for r in query_db("""
            SELECT u.unit_number, u.block, u.floor
            FROM batch_unit bu
            JOIN unit_real u ON bu.unit_id = u.id
            JOIN inspection_batch ib ON bu.batch_id = ib.id
            WHERE bu.inspector_id = ? AND bu.tenant_id = ?
            AND ib.status IN ('open', 'in_progress')
            ORDER BY u.unit_number
        """, [insp['id'], tenant_id])]
        insp['units'] = ', '.join(u['unit_number'] for u in units) if units else 'None'
        insp['login_display'] = insp['last_login'][:16].replace('T', ' ') if insp['last_login'] else 'Never'
        insp['has_logged_in'] = insp['last_login'] is not None

    logged_in = sum(1 for i in inspectors if i['has_logged_in'])

    return render_template('analytics/login_status.html',
        inspectors=inspectors,
        logged_in=logged_in,
        total=len(inspectors))


# ============================================================
# PIPELINE REPORT (Project Overview - unified remediation pipeline)
# ============================================================

def _build_pipeline_report_data(live=False):
    """Build data for the Pipeline Report / Dashboard.
    live=True: current state (dashboard).
    live=False: weekly snapshot (anchor = last Tuesday 00:00 SAST).
    """
    tenant_id = session.get('tenant_id', 'MONOGRAPH')

    from datetime import datetime as _dt, timedelta as _td
    _now_sast = _dt.utcnow() + _td(hours=2)

    if live:
        # Live mode: snapshot = now, ledger = rolling 14 days (matches fortnight cadence)
        snapshot_sast = _now_sast
        snapshot_utc = _dt.utcnow()
        snapshot_str = snapshot_utc.strftime('%Y-%m-%d %H:%M:%S')
        prev_week_utc = snapshot_utc - _td(days=14)
        prev_week_str = prev_week_utc.strftime('%Y-%m-%d %H:%M:%S')
        snapshot_label = 'Live'
        snapshot_date = _now_sast.strftime('%A %d %B %Y')
    else:
        # Default snapshot: last Tuesday 00:00 SAST (= end of last Monday)
        # Ledger window = fortnight (14 days) ending at snapshot, matching bi-weekly meeting cadence
        _days_since_tue = (_now_sast.weekday() - 1) % 7
        snapshot_sast = _now_sast.replace(hour=0, minute=0, second=0, microsecond=0) - _td(days=_days_since_tue)
        snapshot_utc = snapshot_sast - _td(hours=2)
        snapshot_str = snapshot_utc.strftime('%Y-%m-%d %H:%M:%S')
        prev_week_utc = snapshot_utc - _td(days=14)
        prev_week_str = prev_week_utc.strftime('%Y-%m-%d %H:%M:%S')
        snapshot_label = (snapshot_sast - _td(days=1)).strftime('Fortnight ending %A %d %B %Y')
        snapshot_date = (snapshot_sast - _td(days=1)).strftime('%A %d %B %Y')

    # All real units
    all_units = query_db("""
        SELECT id, unit_number, block, floor, certified_at
        FROM unit WHERE tenant_id = ? AND unit_number NOT LIKE 'TEST%'
    """, [tenant_id])
    total_units = len(all_units)

    # Last batch (most recent by created_at) - used for Live-mode batch-scoped movements
    last_batch_row = query_db("""
        SELECT id, name FROM inspection_batch
        WHERE tenant_id = ? ORDER BY created_at DESC LIMIT 1
    """, [tenant_id], one=True)
    last_batch_id = last_batch_row['id'] if last_batch_row else None
    last_batch_name = last_batch_row['name'] if last_batch_row else None

    # Units in active batches (non-removed)
    in_batch_rows = query_db("""
        SELECT DISTINCT bu.unit_id
        FROM batch_unit bu
        JOIN unit u ON bu.unit_id = u.id
        WHERE bu.tenant_id = ? AND u.unit_number NOT LIKE 'TEST%'
        AND bu.removed_at IS NULL
    """, [tenant_id])
    in_batch_ids = set(r['unit_id'] for r in in_batch_rows)

    # Completed inspections: max cycle per unit
    # "completed" = submitted or later in the workflow
    completed_rows = query_db("""
        SELECT i.unit_id, MAX(i.cycle_number) as max_cycle
        FROM inspection i
        JOIN unit_real u ON i.unit_id = u.id
        WHERE i.tenant_id = ?
        AND i.status IN ('reviewed', 'approved', 'pending_followup')
        GROUP BY i.unit_id
    """, [tenant_id])
    unit_max_completed = {r['unit_id']: r['max_cycle'] for r in completed_rows}

    # Any C2+ inspection (any status = under verification)
    c2_rows = query_db("""
        SELECT DISTINCT i.unit_id
        FROM inspection i
        JOIN unit_real u ON i.unit_id = u.id
        WHERE i.tenant_id = ?
        AND i.cycle_number >= 2
    """, [tenant_id])
    c2_plus_ids = set(r['unit_id'] for r in c2_rows)

    # Open defects per unit (as of snapshot)
    open_rows = query_db("""
        SELECT d.unit_id, COUNT(*) as cnt
        FROM defect d
        JOIN unit_real u ON d.unit_id = u.id
        WHERE d.tenant_id = ? AND d.status = 'open'
        AND d.raised_cycle_id NOT LIKE 'test-%%'
        AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
        GROUP BY d.unit_id
    """, [tenant_id])
    unit_open = {r['unit_id']: r['cnt'] for r in open_rows}

    # Headline metrics
    units_inspected = len(unit_max_completed)
    certified_count = sum(1 for u in all_units if u['certified_at'])

    # Cycle efficiency metrics (all None until C2+ data exists)
    metrics = {
        'certified': certified_count,
        'avg_cycles': None,
        'avg_clearance': None,
        'first_time_fix': None,
    }

    # --- MOVEMENTS THIS WEEK ---
    movements = []

    # 1. C1 inspections completed (Live: batch-scope, Snapshot: fortnight window)
    if live and last_batch_id:
        c1_done_rows = query_db("""
            SELECT u.unit_number, u.block, u.floor, i.unit_id,
                (SELECT COUNT(*) FROM defect d WHERE d.unit_id = i.unit_id AND d.status IN ('open','cleared')
                 AND d.raised_cycle_id = i.cycle_id) as defect_count
            FROM inspection i
            JOIN unit_real u ON i.unit_id = u.id
            JOIN batch_unit bu ON bu.unit_id = i.unit_id AND bu.cycle_id = i.cycle_id
                AND bu.tenant_id = i.tenant_id AND bu.batch_id = ?
                AND bu.status != 'removed'
            WHERE i.tenant_id = ? AND i.cycle_number = 1
            AND i.status IN ('reviewed','approved','certified','pending_followup')
            ORDER BY u.block, u.floor, u.unit_number
        """, [last_batch_id, tenant_id])
    else:
        c1_done_rows = query_db("""
            SELECT u.unit_number, u.block, u.floor, i.unit_id,
                (SELECT COUNT(*) FROM defect d WHERE d.unit_id = i.unit_id AND d.status IN ('open','cleared')
                 AND d.raised_cycle_id = i.cycle_id) as defect_count
            FROM inspection i
            JOIN unit_real u ON i.unit_id = u.id
            WHERE i.tenant_id = ? AND i.cycle_number = 1
            AND i.submitted_at > ? AND i.submitted_at <= ?
            AND i.status IN ('reviewed','approved','certified','pending_followup')
            ORDER BY u.block, u.floor, u.unit_number
        """, [tenant_id, prev_week_str, snapshot_str])
    if c1_done_rows:
        from collections import OrderedDict
        zone_groups = OrderedDict()
        for r in c1_done_rows:
            zone = '{} {}'.format(r['block'], FLOOR_LABELS.get(r['floor'], 'Floor {}'.format(r['floor'])))
            if zone not in zone_groups:
                zone_groups[zone] = {'units': [], 'defects': 0}
            zone_groups[zone]['units'].append(r['unit_number'])
            zone_groups[zone]['defects'] += r['defect_count'] or 0
        for zone, data in zone_groups.items():
            movements.append({
                'label': 'Defects Raised',
                'detail': '{} — {} defects raised'.format(zone, data['defects']),
                'units': data['units'],
                'colour': '#C8963E',
            })

    # 2. C2+ de-snag reviewed (Live: batch-scope, Snapshot: fortnight window)
    if live and last_batch_id:
        c2_done_rows = query_db("""
            SELECT u.unit_number, u.block, u.floor, i.unit_id, i.cycle_id,
                (SELECT COUNT(*) FROM defect d WHERE d.unit_id = i.unit_id
                 AND d.status = 'cleared' AND d.cleared_cycle_id = i.cycle_id) as cleared,
                (SELECT COUNT(*) FROM defect d WHERE d.unit_id = i.unit_id
                 AND d.status = 'open') as still_open
            FROM inspection i
            JOIN unit_real u ON i.unit_id = u.id
            JOIN batch_unit bu ON bu.unit_id = i.unit_id AND bu.cycle_id = i.cycle_id
                AND bu.tenant_id = i.tenant_id AND bu.batch_id = ?
                AND bu.status != 'removed'
            WHERE i.tenant_id = ? AND i.cycle_number >= 2
            AND i.status IN ('reviewed','approved','certified','pending_followup')
            ORDER BY u.block, u.floor, u.unit_number
        """, [last_batch_id, tenant_id])
    else:
        c2_done_rows = query_db("""
            SELECT u.unit_number, u.block, u.floor, i.unit_id, i.cycle_id,
                (SELECT COUNT(*) FROM defect d WHERE d.unit_id = i.unit_id
                 AND d.status = 'cleared' AND d.cleared_cycle_id = i.cycle_id) as cleared,
                (SELECT COUNT(*) FROM defect d WHERE d.unit_id = i.unit_id
                 AND d.status = 'open') as still_open
            FROM inspection i
            JOIN unit_real u ON i.unit_id = u.id
            WHERE i.tenant_id = ? AND i.cycle_number >= 2
            AND i.submitted_at > ? AND i.submitted_at <= ?
            AND i.status IN ('reviewed','approved','certified','pending_followup')
            ORDER BY u.block, u.floor, u.unit_number
        """, [tenant_id, prev_week_str, snapshot_str])
    if c2_done_rows:
        from collections import OrderedDict
        zone_groups = OrderedDict()
        for r in c2_done_rows:
            zone = '{} {}'.format(r['block'], FLOOR_LABELS.get(r['floor'], 'Floor {}'.format(r['floor'])))
            if zone not in zone_groups:
                zone_groups[zone] = {'units': [], 'cleared': 0, 'open': 0}
            zone_groups[zone]['units'].append(r['unit_number'])
            zone_groups[zone]['cleared'] += r['cleared'] or 0
            zone_groups[zone]['open'] += r['still_open'] or 0
        for zone, data in zone_groups.items():
            movements.append({
                'label': 'De-snag Reviewed',
                'detail': '{} — {} cleared, {} still open'.format(zone, data['cleared'], data['open']),
                'units': data['units'],
                'colour': '#3D6B8E',
            })

    # 3. Units certified (Live: units in last batch that are certified; Snapshot: fortnight window)
    if live and last_batch_id:
        cert_rows = query_db("""
            SELECT DISTINCT u.unit_number
            FROM unit_real u
            JOIN batch_unit bu ON bu.unit_id = u.id
                AND bu.tenant_id = u.tenant_id AND bu.batch_id = ?
                AND bu.status != 'removed'
            WHERE u.tenant_id = ? AND u.certified_at IS NOT NULL
            ORDER BY u.unit_number
        """, [last_batch_id, tenant_id])
    else:
        cert_rows = query_db("""
            SELECT u.unit_number
            FROM unit_real u
            WHERE u.tenant_id = ? AND u.certified_at > ? AND u.certified_at <= ?
            ORDER BY u.unit_number
        """, [tenant_id, prev_week_str, snapshot_str])
    if cert_rows:
        movements.append({
            'label': 'Certified',
            'detail': '{} units completed'.format(len(cert_rows)),
            'units': [r['unit_number'] for r in cert_rows],
            'colour': '#4A7C59',
        })

    # --- 5-STAGE PIPELINE ---
    pipeline = {'not_requested': 0, 'awaiting': 0, 'defects_raised': 0, 'under_verification': 0, 'certified': 0}
    for u in all_units:
        uid = u['id']
        if u['certified_at']:
            pipeline['certified'] += 1
        elif uid in c2_plus_ids:
            pipeline['under_verification'] += 1
        elif uid in unit_max_completed and unit_open.get(uid, 0) > 0:
            pipeline['defects_raised'] += 1
        elif uid in in_batch_ids:
            pipeline['awaiting'] += 1
        else:
            pipeline['not_requested'] += 1

    # --- ACTIVE BATCHES CALLOUT ---
    active_batch_rows = query_db("""
        SELECT ib.id, ib.name, bu.unit_id
        FROM inspection_batch ib
        JOIN batch_unit bu ON bu.batch_id = ib.id AND bu.status != 'removed'
        JOIN unit u ON bu.unit_id = u.id
        WHERE ib.tenant_id = ?
        AND ib.status = 'complete'
        AND u.unit_number NOT LIKE 'TEST%'
        ORDER BY ib.closed_at DESC
        LIMIT 1
    """, [tenant_id])

    batch_map = {}
    for r in active_batch_rows:
        bid = r['id']
        if bid not in batch_map:
            batch_map[bid] = {'name': r['name'], 'new': 0, 'reinspection': 0}
    # Count new vs re-inspection using cycle_number from inspection_cycle
    for bid in batch_map:
        cycle_counts = query_db("""
            SELECT ic.cycle_number, COUNT(*) as cnt
            FROM batch_unit bu
            JOIN inspection_cycle ic ON bu.cycle_id = ic.id
            JOIN unit u ON bu.unit_id = u.id
            WHERE bu.batch_id = ? AND bu.removed_at IS NULL
            AND u.unit_number NOT LIKE 'TEST%'
            GROUP BY ic.cycle_number
        """, [bid])
        for cc in cycle_counts:
            if cc['cycle_number'] >= 2:
                batch_map[bid]['reinspection'] += cc['cnt']
            else:
                batch_map[bid]['new'] += cc['cnt']

    active_batches = []
    for bid, bdata in batch_map.items():
        total = bdata['new'] + bdata['reinspection']
        parts = []
        if bdata['new'] > 0:
            parts.append(str(bdata['new']) + ' new')
        if bdata['reinspection'] > 0:
            parts.append(str(bdata['reinspection']) + ' de-snag')
        active_batches.append({
            'name': bdata['name'],
            'total': total,
            'detail': ', '.join(parts),
        })

        # --- PAGE 2: DEFECT POOL ---
    from datetime import datetime as _dt, timedelta as _td

    # Find all Mondays from first defect to today
    first_defect = query_db(
        "SELECT MIN(created_at) as d FROM defect WHERE tenant_id = ? AND status IN ('open','cleared')",
        [tenant_id], one=True)
    
    trend_points = []
    if first_defect and first_defect['d']:
        # Find first Monday on or after first defect
        start = _dt.fromisoformat(first_defect['d'].replace('Z', '+00:00') if 'Z' in first_defect['d'] else first_defect['d'])
        days_until_mon = (0 - start.weekday()) % 7
        if days_until_mon == 0 and start.hour > 0:
            days_until_mon = 0  # same day is fine
        first_mon = (start + _td(days=days_until_mon)).replace(hour=23, minute=59, second=59)
        
        today = _dt.now()
        mon = first_mon
        while mon <= today:
            mon_str = mon.strftime('%Y-%m-%d %H:%M:%S')
            raised_row = query_db(
                "SELECT COUNT(*) as c FROM defect d JOIN unit_real u ON d.unit_id = u.id WHERE d.tenant_id = ? AND d.created_at <= ? AND d.raised_cycle_id NOT LIKE 'test-%%' AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))",
                [tenant_id, mon_str], one=True)
            cleared_row = query_db(
                "SELECT COUNT(*) as c FROM defect d JOIN unit_real u ON d.unit_id = u.id WHERE d.tenant_id = ? AND d.status = 'cleared' AND d.cleared_at <= ? AND d.raised_cycle_id NOT LIKE 'test-%%' AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))",
                [tenant_id, mon_str], one=True)
            trend_points.append({
                'date': mon.strftime('%d %b'),
                'raised': raised_row['c'] if raised_row else 0,
                'cleared': cleared_row['c'] if cleared_row else 0,
            })
            mon = mon + _td(days=7)

    # In live mode, add today as final trend point
    if live and trend_points:
        today_str = _dt.now().strftime('%Y-%m-%d %H:%M:%S')
        raised_today = query_db(
            "SELECT COUNT(*) as c FROM defect d JOIN unit_real u ON d.unit_id = u.id WHERE d.tenant_id = ? AND d.created_at <= ? AND d.raised_cycle_id NOT LIKE 'test-%%' AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))",
            [tenant_id, today_str], one=True)
        cleared_today = query_db(
            "SELECT COUNT(*) as c FROM defect d JOIN unit_real u ON d.unit_id = u.id WHERE d.tenant_id = ? AND d.status = 'cleared' AND d.cleared_at <= ? AND d.raised_cycle_id NOT LIKE 'test-%%' AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))",
            [tenant_id, today_str], one=True)
        trend_points.append({
            'date': _dt.now().strftime('%d %b'),
            'raised': raised_today['c'] if raised_today else 0,
            'cleared': cleared_today['c'] if cleared_today else 0,
        })

    # Weekly ledger (prev week -> snapshot)
    last_week_str = prev_week_str
    now_str = snapshot_str
    
    bfwd_row = query_db(
        "SELECT COUNT(*) as c FROM defect d JOIN unit_real u ON d.unit_id = u.id WHERE d.tenant_id = ? AND d.created_at <= ? AND (d.status = 'open' OR (d.status = 'cleared' AND d.cleared_at > ?)) AND d.raised_cycle_id NOT LIKE 'test-%%' AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))",
        [tenant_id, last_week_str, last_week_str], one=True)
    cleared_week_row = query_db(
        "SELECT COUNT(*) as c FROM defect d JOIN unit_real u ON d.unit_id = u.id WHERE d.tenant_id = ? AND d.status = 'cleared' AND d.cleared_at > ? AND d.cleared_at <= ? AND d.raised_cycle_id NOT LIKE 'test-%%' AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))",
        [tenant_id, last_week_str, now_str], one=True)
    new_week_row = query_db(
        "SELECT COUNT(*) as c FROM defect d JOIN unit_real u ON d.unit_id = u.id WHERE d.tenant_id = ? AND d.created_at > ? AND d.created_at <= ? AND d.raised_cycle_id NOT LIKE 'test-%%' AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))",
        [tenant_id, last_week_str, now_str], one=True)
    
    total_open_row = query_db(
        "SELECT COUNT(*) as c FROM defect d JOIN unit_real u ON d.unit_id = u.id WHERE d.tenant_id = ? AND d.created_at <= ? AND (d.status = 'open' OR (d.status = 'cleared' AND d.cleared_at > ?)) AND d.raised_cycle_id NOT LIKE 'test-%%' AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))",
        [tenant_id, snapshot_str, snapshot_str], one=True)
    
    ledger = {
        'bfwd': bfwd_row['c'] if bfwd_row else 0,
        'cleared': cleared_week_row['c'] if cleared_week_row else 0,
        'new': new_week_row['c'] if new_week_row else 0,
        'open': total_open_row['c'] if total_open_row else 0,
    }

    # SVG chart coordinates (600w x 200h chart area)
    chart_w = 600
    chart_h = 200
    svg_points_open = []
    if trend_points:
        max_val = max(p['raised'] - p['cleared'] for p in trend_points) or 1
        n = len(trend_points)
        for i, p in enumerate(trend_points):
            open_val = p['raised'] - p['cleared']
            x = int(60 + (chart_w - 80) * i / max(n - 1, 1))
            y = int(chart_h - 20 - (chart_h - 40) * open_val / max_val)
            svg_points_open.append({'x': x, 'y': y, 'val': open_val, 'date': p['date']})

    # --- PAGE 3: WHERE'S THE PROBLEM ---

    # Zone grid: block x floor — enriched with C1/C2/clearance data

    # Total units per zone (all units, not just inspected)
    zone_total_units_rows = query_db("""
        SELECT u.block, u.floor, COUNT(DISTINCT u.id) as total_units
        FROM unit_real u
        WHERE u.tenant_id = ? AND u.unit_number NOT LIKE 'TEST%%'
        GROUP BY u.block, u.floor
    """, [tenant_id])
    zone_total_units = {}
    for r in zone_total_units_rows:
        zone_total_units[(r['block'], r['floor'])] = r['total_units']

    # C1 inspected units per zone
    zone_c1_rows = query_db("""
        SELECT u.block, u.floor, COUNT(DISTINCT i.unit_id) as c1_inspected
        FROM inspection i
        JOIN unit_real u ON i.unit_id = u.id
        WHERE i.tenant_id = ? AND i.cycle_number = 1
        AND i.status IN ('reviewed','approved','certified','pending_followup')
        AND i.cycle_id NOT LIKE 'test-%%'
        GROUP BY u.block, u.floor
    """, [tenant_id])
    zone_c1 = {}
    for r in zone_c1_rows:
        zone_c1[(r['block'], r['floor'])] = r['c1_inspected']

    # C2+ units per zone (units with any C2+ inspection)
    zone_c2_rows = query_db("""
        SELECT u.block, u.floor, COUNT(DISTINCT i.unit_id) as c2_units
        FROM inspection i
        JOIN unit_real u ON i.unit_id = u.id
        WHERE i.tenant_id = ? AND i.cycle_number >= 2
        AND i.cycle_id NOT LIKE 'test-%%'
        GROUP BY u.block, u.floor
    """, [tenant_id])
    zone_c2 = {}
    for r in zone_c2_rows:
        zone_c2[(r['block'], r['floor'])] = r['c2_units']

    # Total raised defects per zone (all time up to snapshot, from completed inspections)
    zone_raised_rows = query_db("""
        SELECT u.block, u.floor, COUNT(*) as raised
        FROM defect d
        JOIN unit_real u ON d.unit_id = u.id
        WHERE d.tenant_id = ?
        AND d.raised_cycle_id NOT LIKE 'test-%%'
        AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id
                    AND i2.status IN ('reviewed','approved','certified','pending_followup'))
        GROUP BY u.block, u.floor
    """, [tenant_id])
    zone_raised = {}
    for r in zone_raised_rows:
        zone_raised[(r['block'], r['floor'])] = r['raised']

    # Cleared defects per zone (as of snapshot)
    zone_cleared_rows = query_db("""
        SELECT u.block, u.floor, COUNT(*) as cleared
        FROM defect d
        JOIN unit_real u ON d.unit_id = u.id
        WHERE d.tenant_id = ? AND d.status = 'cleared'
        AND d.raised_cycle_id NOT LIKE 'test-%%'
        AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id
                    AND i2.status IN ('reviewed','approved','certified','pending_followup'))
        GROUP BY u.block, u.floor
    """, [tenant_id])
    zone_cleared = {}
    for r in zone_cleared_rows:
        zone_cleared[(r['block'], r['floor'])] = r['cleared']

    # Open defects per zone (as of snapshot)
    zone_open_rows = query_db("""
        SELECT u.block, u.floor, COUNT(*) as cnt
        FROM defect d
        JOIN unit_real u ON d.unit_id = u.id
        WHERE d.tenant_id = ? AND d.status = 'open'
        AND d.raised_cycle_id NOT LIKE 'test-%%'
        AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id
                    AND i2.status IN ('reviewed','approved','certified','pending_followup'))
        GROUP BY u.block, u.floor
    """, [tenant_id])
    zone_open = {}
    for r in zone_open_rows:
        zone_open[(r['block'], r['floor'])] = r['cnt']

    # Build enriched zone grid
    all_blocks = sorted(set(k[0] for k in zone_total_units))
    all_floors = sorted(set(k[1] for k in zone_total_units))
    zone_map = {}
    for key in zone_total_units:
        total = zone_total_units[key]
        c1 = zone_c1.get(key, 0)
        c2 = zone_c2.get(key, 0)
        raised = zone_raised.get(key, 0)
        cleared = zone_cleared.get(key, 0)
        opn = zone_open.get(key, 0)
        avg = round(raised / c1, 1) if c1 > 0 else 0
        clearance_pct = round(cleared / raised * 100, 1) if raised > 0 else 0

        # Stage logic
        if c1 == 0:
            stage = 'not_inspected'
        elif c2 > 0 and clearance_pct >= 80:
            stage = 'near_complete'
        elif c2 > 0:
            stage = 'desnag'
        else:
            stage = 'awaiting'

        zone_map[key] = {
            'total_units': total,
            'c1_inspected': c1,
            'c2_units': c2,
            'raised': raised,
            'cleared': cleared,
            'cnt': opn,
            'avg': avg,
            'clearance_pct': clearance_pct,
            'stage': stage,
            'units': c1,
        }

    project_avg = round(
        sum(v['raised'] for v in zone_map.values()) /
        sum(v['c1_inspected'] for v in zone_map.values()), 1
    ) if sum(v['c1_inspected'] for v in zone_map.values()) > 0 else 0

    zone_grid = {
        'blocks': all_blocks,
        'floors': all_floors,
        'data': zone_map,
        'project_avg': project_avg,
    }

    # Floor label helper
    floor_labels = {0: 'Ground', 1: '1st Floor', 2: '2nd Floor'}

    # Area breakdown (by room)
    area_rows = query_db("""
        SELECT at2.area_name, COUNT(*) as cnt
        FROM defect d
        JOIN unit_real u ON d.unit_id = u.id
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at2 ON ct.area_id = at2.id
        WHERE d.tenant_id = ? AND d.status = 'open'
        AND d.raised_cycle_id NOT LIKE 'test-%%'
        AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
        GROUP BY at2.area_name
        ORDER BY cnt DESC
    """, [tenant_id])

    total_open = ledger['open']
    areas = []
    for r in area_rows:
        pct = round(100 * r['cnt'] / total_open, 1) if total_open > 0 else 0
        areas.append({
            'name': r['area_name'],
            'count': r['cnt'],
            'pct': pct,
        })

    # Trade breakdown (by category)
    trade_rows = query_db("""
        SELECT ct.category_name, COUNT(*) as cnt
        FROM defect d
        JOIN unit_real u ON d.unit_id = u.id
        JOIN item_template it ON d.item_template_id = it.id
        JOIN category_template ct ON it.category_id = ct.id
        WHERE d.tenant_id = ? AND d.status = 'open'
        AND d.raised_cycle_id NOT LIKE 'test-%%'
        AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
        GROUP BY ct.category_name
        ORDER BY cnt DESC
    """, [tenant_id])

    trades = []
    for r in trade_rows:
        pct = round(100 * r['cnt'] / total_open, 1) if total_open > 0 else 0
        trades.append({
            'name': r['category_name'],
            'count': r['cnt'],
            'pct': pct,
        })

    # --- AREA DEEP DIVE (top 3 defects in top 2 areas) ---
    area_deep_dive = []
    dd_colours = ['#C8963E', '#3D6B8E']
    for idx, area_row in enumerate(areas[:2]):
        area_name = area_row['name']
        area_defects = [dict(r) for r in query_db("""
            SELECT d.original_comment AS description, COUNT(*) AS count
            FROM defect d
            JOIN unit_real u ON d.unit_id = u.id
            JOIN item_template it ON d.item_template_id = it.id
            JOIN category_template ct ON it.category_id = ct.id
            JOIN area_template at2 ON ct.area_id = at2.id
            WHERE d.tenant_id = ? AND d.status = 'open'
            AND d.raised_cycle_id NOT LIKE 'test-%%'
            AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
            AND at2.area_name = ?
            GROUP BY d.original_comment
            ORDER BY count DESC
            LIMIT 3
        """, [tenant_id, area_name])]
        max_dd = area_defects[0]['count'] if area_defects else 1
        for d in area_defects:
            d['bar_pct'] = round(d['count'] / max_dd * 100)
        area_deep_dive.append({
            'area': area_name,
            'total': area_row['count'],
            'pct': area_row['pct'],
            'colour': dd_colours[idx],
            'defects': area_defects,
        })

    dd_callout = ''
    if len(area_deep_dive) >= 1 and area_deep_dive[0]['defects']:
        a1 = area_deep_dive[0]
        d1 = a1['defects'][0]
        dd_callout = 'The most frequent defect in {} is {} ({} occurrences).'.format(
            a1['area'].title(), d1['description'].lower(), d1['count'])
        if len(area_deep_dive) >= 2 and area_deep_dive[1]['defects']:
            a2 = area_deep_dive[1]
            d2 = a2['defects'][0]
            dd_callout += ' In {}, {} leads with {} occurrences.'.format(
                a2['area'].title(), d2['description'].lower(), d2['count'])

    # --- SYSTEMIC ISSUES (recurring defects across 3+ units) ---
    recurring_raw = query_db("""
        SELECT d.original_comment,
            COUNT(d.id) AS cnt,
            COUNT(DISTINCT d.unit_id) AS unit_count
        FROM defect d
        JOIN unit_real u ON d.unit_id = u.id
        WHERE d.tenant_id = ? AND d.status = 'open'
        AND d.raised_cycle_id NOT LIKE 'test-%%'
        AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
        GROUP BY d.original_comment
        HAVING unit_count >= 3
        ORDER BY cnt DESC
        LIMIT 10
    """, [tenant_id])
    recurring = [dict(r) for r in recurring_raw]

    if recurring:
        top_comments = [r['original_comment'] for r in recurring]
        placeholders = ','.join('?' * len(top_comments))
        cat_raw = query_db("""
            SELECT d.original_comment, ct.category_name, COUNT(d.id) AS cat_cnt
            FROM defect d
            JOIN unit_real u ON d.unit_id = u.id
            JOIN item_template it ON d.item_template_id = it.id
            JOIN category_template ct ON it.category_id = ct.id
            WHERE d.tenant_id = ? AND d.status = 'open'
            AND d.raised_cycle_id NOT LIKE 'test-%%'
            AND d.original_comment IN ({})
            AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
            GROUP BY d.original_comment, ct.category_name
            ORDER BY d.original_comment, cat_cnt DESC
        """.format(placeholders), [tenant_id] + top_comments)
        from collections import defaultdict
        cat_map = defaultdict(list)
        for row in cat_raw:
            cat_map[row['original_comment']].append({'cat': row['category_name'], 'cnt': row['cat_cnt']})
        for r in recurring:
            r['cat_breakdown'] = cat_map.get(r['original_comment'], [])

    # --- DE-SNAG RESULTS ---

    desnag = None
    desnag_unit_rows = query_db("""
        SELECT u.id as unit_id, u.unit_number, u.block, u.floor,
               MAX(i.cycle_number) as max_cycle
        FROM inspection i
        JOIN unit_real u ON i.unit_id = u.id
        WHERE i.tenant_id = ? AND i.cycle_number >= 2
        AND i.status IN ('reviewed','approved','certified','pending_followup')
        AND i.cycle_id NOT LIKE 'test-%%'
        GROUP BY u.id
        ORDER BY u.unit_number
    """, [tenant_id])

    if desnag_unit_rows:
        desnag_units = []
        total_bfwd = 0
        total_cleared = 0
        total_still_open = 0
        total_regressions = 0
        fully_cleared_count = 0

        for row in desnag_unit_rows:
            uid = row['unit_id']
            mc = row['max_cycle']
            counts = query_db("""
                SELECT
                    SUM(CASE WHEN d.raised_cycle_number < ? THEN 1 ELSE 0 END) as bfwd,
                    SUM(CASE WHEN d.status = 'cleared' AND d.cleared_cycle_number >= 2 THEN 1 ELSE 0 END) as cleared,
                    SUM(CASE WHEN d.raised_cycle_number >= 2 THEN 1 ELSE 0 END) as regressions
                FROM defect d
                WHERE d.unit_id = ? AND d.tenant_id = ?
                AND d.raised_cycle_id NOT LIKE 'test-%%'
            """, [mc, uid, tenant_id], one=True)

            bfwd = counts['bfwd'] or 0
            cleared = counts['cleared'] or 0
            still_open = bfwd - cleared
            regressions = counts['regressions'] or 0
            rate = round(cleared / bfwd * 100, 1) if bfwd > 0 else 0

            fl = FLOOR_LABELS.get(row['floor'], 'Floor {}'.format(row['floor']))
            desnag_units.append({
                'unit': row['unit_number'],
                'zone': '{} {}'.format(row['block'], fl),
                'bfwd': bfwd,
                'cleared': cleared,
                'open': still_open,
                'rate': rate,
                'cycle': mc,
                'regressions': regressions,
            })

            total_bfwd += bfwd
            total_cleared += cleared
            total_still_open += still_open
            total_regressions += regressions
            if still_open == 0:
                fully_cleared_count += 1

        desnag_units.sort(key=lambda x: x['rate'])

        desnag_eligible_row = query_db("""
            SELECT COUNT(DISTINCT d.unit_id) as cnt
            FROM defect d
            JOIN unit_real u ON d.unit_id = u.id
            WHERE d.tenant_id = ? AND d.raised_cycle_number = 1
            AND d.raised_cycle_id NOT LIKE 'test-%%'
            AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id
                        AND i2.cycle_number = 1 AND i2.tenant_id = d.tenant_id
                        AND i2.status IN ('reviewed','approved','certified','pending_followup'))
        """, [tenant_id], one=True)
        desnag_eligible = desnag_eligible_row['cnt'] if desnag_eligible_row else 0

        overall_rate = round(total_cleared / total_bfwd * 100, 1) if total_bfwd > 0 else 0

        desnag = {
            'units': desnag_units,
            'count': len(desnag_units),
            'eligible': desnag_eligible,
            'total_bfwd': total_bfwd,
            'total_cleared': total_cleared,
            'total_still_open': total_still_open,
            'total_regressions': total_regressions,
            'fully_cleared': fully_cleared_count,
            'clearance_rate': overall_rate,
        }


    # --- PAGE 4: STUCK UNITS ---

    # All units with open defects + their C1 submission date + cycle info
    stuck_rows = query_db("""
        SELECT u.unit_number, u.block, u.floor,
               COUNT(d.id) as open_count,
               (SELECT MIN(i.submitted_at) FROM inspection i WHERE i.unit_id = u.id AND i.tenant_id = d.tenant_id AND i.status IN ('reviewed','approved','pending_followup')) as first_c1_submitted,
               (SELECT MAX(i.cycle_number) FROM inspection i WHERE i.unit_id = u.id AND i.tenant_id = d.tenant_id AND i.status IN ('reviewed','approved','pending_followup')) as max_cycle,
               SUM(CASE WHEN d.raised_cycle_number >= 2 THEN 1 ELSE 0 END) as new_c2
        FROM defect d
        JOIN unit_real u ON d.unit_id = u.id
        WHERE d.tenant_id = ? AND d.status = 'open'
        AND d.raised_cycle_id NOT LIKE 'test-%%'
        AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id AND i2.cycle_id = d.raised_cycle_id AND i2.status IN ('reviewed','approved','certified','pending_followup'))
        GROUP BY u.id
        ORDER BY open_count DESC
    """, [tenant_id])

    stuck_units = []
    total_stuck_defects = 0
    oldest_weeks = 0
    for r in stuck_rows:
        weeks = 0
        if r['first_c1_submitted']:
            try:
                sub_dt = _dt.fromisoformat(r['first_c1_submitted'].replace('Z', '+00:00') if 'Z' in r['first_c1_submitted'] else r['first_c1_submitted'])
                weeks = max(0, (_dt.now(sub_dt.tzinfo) - sub_dt).days // 7) if sub_dt.tzinfo else max(0, (_dt.now() - sub_dt).days // 7)
            except (ValueError, TypeError):
                weeks = 0
        if weeks > oldest_weeks:
            oldest_weeks = weeks
        total_stuck_defects += r['open_count']
        floor_lbl = floor_labels.get(r['floor'], str(r['floor']))
        stuck_units.append({
            'unit': r['unit_number'],
            'zone': '{} {}'.format(r['block'], floor_lbl),
            'cycle': r['max_cycle'] or 1,
            'open': r['open_count'],
            'weeks': weeks,
            'new_c2': r['new_c2'] or 0,
        })

    avg_per_unit = round(total_stuck_defects / len(stuck_units), 0) if stuck_units else 0

    stuck_headline = {
        'worst_unit': stuck_units[0]['unit'] if stuck_units else None,
        'worst_count': stuck_units[0]['open'] if stuck_units else 0,
        'avg_per_unit': int(avg_per_unit),
        'oldest_weeks': oldest_weeks,
    }

    # Hot Spots data: area median, quartiles for unit coloring
    area_counts_list = [a['count'] for a in areas]
    if area_counts_list:
        area_counts_sorted_hs = sorted(area_counts_list)
        mid_a = len(area_counts_sorted_hs) // 2
        area_median = area_counts_sorted_hs[mid_a] if len(area_counts_sorted_hs) % 2 else (area_counts_sorted_hs[mid_a-1] + area_counts_sorted_hs[mid_a]) / 2
    else:
        area_median = 0
    area_max = areas[0]['count'] if areas else 1

    area_top2_sum = sum(a['count'] for a in areas[:2]) if len(areas) >= 2 else 0
    area_top2_pct = round(area_top2_sum / total_open * 100) if total_open > 0 else 0
    area_top2_names = [a['name'].title() for a in areas[:2]] if len(areas) >= 2 else []

    unit_defect_counts = sorted([u['open'] for u in stuck_units]) if stuck_units else []
    def _pctl(data, pct):
        if not data:
            return 0
        k = (len(data) - 1) * pct / 100
        lo = int(k)
        hi = lo + 1
        if hi >= len(data):
            return data[lo]
        return data[lo] + (data[hi] - data[lo]) * (k - lo)
    q1 = round(_pctl(unit_defect_counts, 25), 1)
    q3 = round(_pctl(unit_defect_counts, 75), 1)

    # Additional KPI metrics (snapshot-based)
    # Median defects per unit
    defect_counts_sorted = sorted([u['open'] for u in stuck_units]) if stuck_units else []
    if defect_counts_sorted:
        mid = len(defect_counts_sorted) // 2
        median_defects = defect_counts_sorted[mid] if len(defect_counts_sorted) % 2 else round((defect_counts_sorted[mid-1] + defect_counts_sorted[mid]) / 2, 1)
    else:
        median_defects = 0

    # Defect rate: total open defects / items inspected (units * 509)
    items_inspected = units_inspected * 509
    total_open_defects = ledger['open']
    defect_rate = round(total_open_defects / items_inspected * 100, 1) if items_inspected > 0 else 0

    # Est C1 complete: based on weekly inspection rate up to snapshot
    weeks_elapsed = len(trend_points) if trend_points else 1
    rate_per_week = round(units_inspected / max(weeks_elapsed, 1), 1)
    units_remaining = total_units - units_inspected
    if rate_per_week > 0:
        weeks_to_go = units_remaining / rate_per_week
        from datetime import date as _date
        est_complete = snapshot_sast.date() + _td(weeks=weeks_to_go)
        est_complete_str = est_complete.strftime('%d %b %Y')
    else:
        est_complete_str = None

    kpi = {
        'units_inspected': units_inspected,
        'total_units': total_units,
        'pct_complete': round(units_inspected / total_units * 100) if total_units else 0,
        'open_defects': total_open_defects,
        'certified': metrics['certified'],
        'avg_per_unit': stuck_headline['avg_per_unit'],
        'median_per_unit': median_defects,
        'defect_rate': defect_rate,
        'items_inspected': items_inspected,
        'worst_unit': stuck_headline['worst_unit'],
        'worst_count': stuck_headline['worst_count'],
        'est_complete': est_complete_str,
        'units_remaining': units_remaining,
        'rate_per_week': rate_per_week,
    }

    # --- POOL TREND (avg net change over last 4 weeks) ---
    pool_trend = {'direction': 'stable', 'avg_change': 0, 'weeks': 0}
    if len(trend_points) >= 2:
        recent = trend_points[-4:]  # last 4 (or fewer)
        deltas = []
        for i in range(1, len(recent)):
            open_prev = recent[i-1]['raised'] - recent[i-1]['cleared']
            open_curr = recent[i]['raised'] - recent[i]['cleared']
            deltas.append(open_curr - open_prev)
        if deltas:
            avg_change = round(sum(deltas) / len(deltas))
            pool_trend = {
                'direction': 'growing' if avg_change > 0 else 'shrinking' if avg_change < 0 else 'stable',
                'avg_change': abs(avg_change),
                'weeks': len(deltas),
            }

    # --- STUCK UNITS SORT (cycle desc, then open desc) ---
    stuck_units.sort(key=lambda x: -x['open'])

    return {
        'units_inspected': units_inspected,
        'metrics': metrics,
        'movements': movements,
        'total_units': total_units,
        'trend_points': trend_points,
        'ledger': ledger,
        'svg_open': svg_points_open,
        'chart_w': chart_w,
        'chart_h': chart_h,
        'zone_grid': zone_grid,
        'floor_labels': floor_labels,
        'areas': areas,
        'trades': trades,
        'active_batches': active_batches,
        'stuck_units': stuck_units,
        'stuck_headline': stuck_headline,
        'area_deep_dive': area_deep_dive,
        'dd_callout': dd_callout,
        'recurring': recurring,
        'area_median': area_median,
        'area_max': area_max,
        'area_top2_pct': area_top2_pct,
        'area_top2_names': area_top2_names,
        'q1': q1,
        'q3': q3,
        'snapshot_label': snapshot_label,
        'snapshot_date': snapshot_date,
        'ledger_from': (snapshot_utc - _td(days=7) + _td(hours=2)).strftime('%d %b'),
        'ledger_to': (snapshot_utc + _td(hours=2) - _td(days=1)).strftime('%d %b %Y'),
        'kpi': kpi,
        'pipeline': pipeline,
        'pool_trend': pool_trend,
        'desnag': desnag,
        'last_batch_id': last_batch_id,
        'last_batch_name': last_batch_name,
    }


@analytics_bp.route('/pipeline')
@require_manager
def pipeline_report_view():
    """Pipeline Report - HTML preview."""
    import datetime, base64, os as _os
    from flask import current_app
    data = _build_pipeline_report_data()
    data['is_pdf'] = False
    data['report_date'] = datetime.datetime.now().strftime('%d %B %Y')
    logo_path = _os.path.join(current_app.static_folder, 'monograph_logo.jpg')
    if _os.path.exists(logo_path):
        with open(logo_path, 'rb') as f:
            data['logo_b64'] = base64.b64encode(f.read()).decode()
    else:
        data['logo_b64'] = ''
    return render_template('analytics/pipeline_report.html', **data)


@analytics_bp.route('/pipeline/pdf')
@require_manager
def pipeline_report_pdf():
    """Pipeline Report - PDF download."""
    from app.services.pdf_playwright import html_to_pdf
    import datetime, base64, os as _os
    from flask import current_app
    data = _build_pipeline_report_data()
    data['is_pdf'] = True
    data['report_date'] = datetime.datetime.now().strftime('%d %B %Y')
    logo_path = _os.path.join(current_app.static_folder, 'monograph_logo.jpg')
    if _os.path.exists(logo_path):
        with open(logo_path, 'rb') as f:
            data['logo_b64'] = base64.b64encode(f.read()).decode()
    else:
        data['logo_b64'] = ''
    html_str = render_template('analytics/pipeline_report.html', **data)
    footer = '''<div style="width: 100%; font-size: 8px; font-family: 'DM Sans', Helvetica, Arial, sans-serif; padding: 0 16mm; display: flex; justify-content: space-between; color: #9A9A9A;">
        <span>Confidential &mdash; Monograph Architects</span>
        <span>Power Park Student Housing &ndash; Phase 3</span>
        <span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
    </div>'''
    pdf_bytes = html_to_pdf(html_str, footer_template=footer)
    resp = make_response(pdf_bytes)
    resp.headers['Content-Type'] = 'application/pdf'
    resp.headers['Content-Disposition'] = 'attachment; filename=Pipeline_Report_{}.pdf'.format(
        datetime.datetime.now().strftime('%Y%m%d'))
    return resp


@analytics_bp.route('/pipeline/dashboard')
@require_manager
def pipeline_dashboard():
    """Pipeline Dashboard - mirror of Pipeline PDF with live/snapshot toggle."""
    mode = request.args.get('mode', 'live')
    is_live = (mode == 'live')
    data = _build_pipeline_report_data(live=is_live)
    data['mode'] = 'live' if is_live else 'snapshot'
    return render_template('analytics/pipeline_dashboard.html', **data)
