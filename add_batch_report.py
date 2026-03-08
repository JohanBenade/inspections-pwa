import os
import sys

fpath = os.path.expanduser('~/Documents/GitHub/inspections-pwa/app/routes/analytics.py')
with open(fpath, 'r') as f:
    content = f.read()

# Anchor: unique string at end of unified_report_pdf, before _build_combined_report_data
FIND = """    response.headers['Content-Disposition'] = 'attachment; filename=PPSH_Project_Report_{}.pdf'.format(
        data['report_date'].replace(' ', '_'))
    return response


def _build_combined_report_data():"""

if FIND not in content:
    print("ERROR: anchor string not found")
    sys.exit(1)

count = content.count(FIND)
if count != 1:
    print(f"ERROR: anchor found {count} times, expected 1")
    sys.exit(1)

NEW_CODE = '''
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
    """Batch inspection report - PDF download via WeasyPrint."""
    from weasyprint import HTML
    data = _build_batch_report_data(batch_id)
    if data is None:
        return "Batch not found or no data.", 404
    data['is_pdf'] = True
    html_str = render_template('analytics/report_batch.html', **data)
    pdf_bytes = HTML(string=html_str, base_url=request.url_root).write_pdf()
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
            JOIN unit u ON i.unit_id = u.id
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
            JOIN unit u ON bu.unit_id = u.id
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
        "SELECT u.unit_number, u.block, u.floor, COUNT(d.id) as defect_count "
        "FROM defect d JOIN unit u ON d.unit_id = u.id "
        "WHERE d.tenant_id = ? AND d.status = 'open' "
        "AND d.unit_id IN (SELECT unit_id FROM batch_unit WHERE batch_id = ? AND removed_at IS NULL AND tenant_id = ?) "
        "AND d.raised_cycle_id IN ({}) "
        "AND EXISTS (SELECT 1 FROM inspection i2 WHERE i2.unit_id = d.unit_id "
        "AND i2.cycle_id = d.raised_cycle_id "
        "AND i2.status IN ('reviewed','approved','certified','pending_followup')) "
        "GROUP BY u.id ORDER BY defect_count DESC LIMIT 5".format(ph),
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
        "FROM defect d JOIN unit u ON d.unit_id = u.id "
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
    }

'''

REPLACE = """    response.headers['Content-Disposition'] = 'attachment; filename=PPSH_Project_Report_{}.pdf'.format(
        data['report_date'].replace(' ', '_'))
    return response

""" + NEW_CODE + """

def _build_combined_report_data():"""

new_content = content.replace(FIND, REPLACE)

if new_content == content:
    print("ERROR: replacement produced no change")
    sys.exit(1)

with open(fpath, 'w') as f:
    f.write(new_content)

print("SUCCESS: analytics.py updated")
print(f"Original length: {len(content)}")
print(f"New length: {len(new_content)}")
