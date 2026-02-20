@analytics_bp.route('/')
@require_manager
def dashboard():
    """Analytics Dashboard - block+floor cards with project overview."""
    tenant_id = session.get('tenant_id', 'MONOGRAPH')

    # 1. Unit counts per block+floor
    unit_counts_raw = query_db("""
        SELECT u.block, u.floor, COUNT(DISTINCT u.id) as total_units
        FROM unit u
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
        JOIN unit u ON d.unit_id = u.id
        WHERE d.tenant_id = ? AND d.status = 'open'
        AND d.raised_cycle_id NOT LIKE 'test-%'
        GROUP BY u.block, u.floor
    """, [tenant_id])
    defect_map = {}
    for r in defect_counts_raw:
        defect_map[(r['block'], r['floor'])] = r['open_defects']

    # 3. Round breakdown per block+floor
    rounds_raw = query_db("""
        SELECT ic.block, ic.floor, ic.cycle_number as round_number,
            COUNT(DISTINCT i.unit_id) as units_inspected
        FROM inspection i
        JOIN inspection_cycle ic ON i.cycle_id = ic.id
        WHERE i.tenant_id = ? AND i.cycle_id NOT LIKE 'test-%'
        AND i.status NOT IN ('not_started')
        GROUP BY ic.block, ic.floor, ic.cycle_number
        ORDER BY ic.block, ic.floor, ic.cycle_number
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
        JOIN unit u ON i.unit_id = u.id
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
        JOIN unit u ON i.unit_id = u.id
        WHERE i.tenant_id = ? AND i.cycle_id NOT LIKE 'test-%'
        AND i.status NOT IN ('not_started')
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
        WHERE i.tenant_id = ? AND i.cycle_id NOT LIKE 'test-%'
        AND i.status NOT IN ('not_started')
    """, [tenant_id], one=True)
    units_inspected = inspected_raw['inspected'] if inspected_raw else 0
    items_inspected = ITEMS_PER_UNIT * units_inspected
    project['units_inspected'] = units_inspected
    project['pct_complete'] = round(units_inspected / PROJECT_TOTAL_UNITS * 100) if PROJECT_TOTAL_UNITS > 0 else 0
    project['avg_defects_inspected'] = round(total_defects_project / units_inspected, 1) if units_inspected > 0 else 0
    project['defect_rate_inspected'] = round(total_defects_project / items_inspected * 100, 1) if items_inspected > 0 else 0
    project['items_inspected'] = items_inspected
    project['project_total'] = PROJECT_TOTAL_UNITS

    # 7b. Median, min, max defects per unit (inspected only)
    unit_defect_counts_raw = query_db("""
        SELECT COUNT(d.id) as defect_count
        FROM inspection i
        JOIN unit u ON i.unit_id = u.id
        LEFT JOIN defect d ON d.unit_id = u.id AND d.status = 'open'
            AND d.raised_cycle_id NOT LIKE 'test-%' AND d.tenant_id = u.tenant_id
        WHERE i.tenant_id = ? AND i.cycle_id NOT LIKE 'test-%'
        AND i.status NOT IN ('not_started')
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

    # 8. Rectification pulse (R2+ data)
    rect_raw = query_db("""
        SELECT
            COUNT(*) as total_reviewed,
            SUM(CASE WHEN d.status = 'cleared' AND d.clearance_note = 'rectified' THEN 1 ELSE 0 END) as rectified,
            SUM(CASE WHEN d.status = 'cleared' AND d.clearance_note = 'superseded' THEN 1 ELSE 0 END) as superseded
        FROM defect d
        JOIN inspection_cycle ic ON d.raised_cycle_id = ic.id
        WHERE d.tenant_id = ? AND ic.id NOT LIKE 'test-%'
        AND d.status = 'cleared' AND d.clearance_note IS NOT NULL
    """, [tenant_id], one=True)

    r2_units_raw = query_db("""
        SELECT COUNT(DISTINCT i.unit_id) as r2_units
        FROM inspection i
        JOIN inspection_cycle ic ON i.cycle_id = ic.id
        WHERE i.tenant_id = ? AND ic.cycle_number > 1
        AND ic.id NOT LIKE 'test-%' AND i.status NOT IN ('not_started')
    """, [tenant_id], one=True)

    r2_new_raw = query_db("""
        SELECT COUNT(*) as new_defects
        FROM defect d
        JOIN inspection_cycle ic ON d.raised_cycle_id = ic.id
        WHERE d.tenant_id = ? AND ic.cycle_number > 1
        AND ic.id NOT LIKE 'test-%' AND d.status = 'open'
    """, [tenant_id], one=True)

    rectification = None
    r2_units = r2_units_raw['r2_units'] if r2_units_raw else 0
    if r2_units > 0:
        rectified = rect_raw['rectified'] or 0 if rect_raw else 0
        superseded = rect_raw['superseded'] or 0 if rect_raw else 0
        total_cleared = rectified + superseded
        r2_new = r2_new_raw['new_defects'] or 0 if r2_new_raw else 0
        clearance_pct = round(rectified / total_cleared * 100, 1) if total_cleared > 0 else 0
        rectification = {
            'r2_units': r2_units,
            'total_reviewed': total_cleared,
            'rectified': rectified,
            'superseded': superseded,
            'new_defects': r2_new,
            'clearance_pct': clearance_pct,
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
        GROUP BY at2.area_name
        ORDER BY defect_count DESC
    """, [tenant_id])]
    area_max = area_data[0]['defect_count'] if area_data else 1

    # 10. Worst units (top 5)
    worst_units = [dict(r) for r in query_db("""
        SELECT u.unit_number, u.block, u.floor,
               COUNT(d.id) as defect_count
        FROM defect d
        JOIN unit u ON d.unit_id = u.id
        WHERE d.tenant_id = ? AND d.status = 'open'
        AND d.raised_cycle_id NOT LIKE 'test-%'
        GROUP BY u.id, u.unit_number, u.block, u.floor
        ORDER BY defect_count DESC
        LIMIT 5
    """, [tenant_id])]

    # Separate active vs awaiting blocks (a block is active if ANY zone has inspections)
    active_blocks = set()
    for card in cards:
        if card['inspected'] > 0:
            active_blocks.add(card['block'])

    return render_template('analytics/dashboard_v2.html',
                           has_data=True,
                           cards=cards,
                           project=project,
                           rectification=rectification,
                           area_data=area_data,
                           area_max=area_max,
                           area_colours=AREA_COLOURS,
                           worst_units=worst_units,
                           active_blocks=active_blocks,
                           floor_labels=FLOOR_LABELS)
