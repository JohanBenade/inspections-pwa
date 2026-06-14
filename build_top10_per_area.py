def _build_top10_per_area_data():
    """Build context for the "Top 10 defects per area" C1 build-quality brief.

    Audience: Raubex + Aurelius (developer); secondary Kevin.
    Scope: C1 defects only (raised_cycle_number = 1), all 4-Bed units in PH3
    with a C1 inspection at status 'pending_followup'. Bedrooms A-D merged into
    one logical "BEDROOMS" group.

    Reuse note: cohort / denominator / comment logic mirrors _build_top_50_data
    exactly. The structural difference is the grouping key: this report groups
    by (room_group, item_description, trade) -- collapsing BEDROOM A/B/C/D and
    their 4 per-bedroom item_template rows into one logical item -- and ranks by
    units-affected (COUNT(DISTINCT unit_id)) rather than raw count.

    Units-affected rule (locked, matches SPECS_OPEN s1): a defect present in 3
    of a unit's 4 bedrooms = 1 unit affected; total-logged still counts all 3.
    """
    from collections import defaultdict, OrderedDict
    tenant_id = session.get('tenant_id', 'MONOGRAPH')
    phase_id = 'phase-003'

    # --- Cohort: 4-Bed units in PH3 with a C1 inspection at pending_followup ---
    cohort_row = query_db("""
        SELECT COUNT(*) AS n FROM unit u
        WHERE u.tenant_id = ? AND u.phase_id = ? AND u.unit_type = '4-Bed'
        AND EXISTS (
            SELECT 1 FROM inspection i
            WHERE i.unit_id = u.id AND i.tenant_id = ?
            AND i.cycle_number = 1 AND i.status = 'pending_followup'
        )
    """, [tenant_id, phase_id, tenant_id], one=True)
    cohort_units = cohort_row['n'] if cohort_row else 0

    # --- Total 4-Bed units in PH3 (denominator), TEST excluded ---
    total_row = query_db("""
        SELECT COUNT(*) AS n FROM unit u
        WHERE u.tenant_id = ? AND u.phase_id = ? AND u.unit_type = '4-Bed'
        AND u.unit_number NOT LIKE 'TEST%'
    """, [tenant_id, phase_id], one=True)
    total_4bed_units = total_row['n'] if total_row else 0

    # --- Total C1 defects across cohort ---
    total_defects_row = query_db("""
        SELECT COUNT(*) AS n FROM defect d
        WHERE d.tenant_id = ? AND d.raised_cycle_number = 1
        AND d.unit_id IN (
            SELECT u.id FROM unit u
            WHERE u.tenant_id = ? AND u.phase_id = ? AND u.unit_type = '4-Bed'
            AND EXISTS (
                SELECT 1 FROM inspection i
                WHERE i.unit_id = u.id AND i.tenant_id = ?
                AND i.cycle_number = 1 AND i.status = 'pending_followup'
            )
        )
    """, [tenant_id, tenant_id, phase_id, tenant_id], one=True)
    total_defects = total_defects_row['n'] if total_defects_row else 0

    avg_per_unit = round(total_defects / cohort_units) if cohort_units > 0 else 0

    # --- Raw rows: one per (unit, defect) with item/trade/area attached. ---
    # We pull defect-level rows (not pre-grouped) so the bedroom merge and the
    # COUNT(DISTINCT unit_id) dedupe can be done in Python on the logical key.
    raw_rows = query_db("""
        SELECT d.unit_id AS unit_id,
               it.item_description AS item,
               ct.category_name AS trade,
               a.area_name AS area,
               COALESCE(NULLIF(TRIM(d.original_comment), ''), '(blank)') AS cmt
        FROM defect d
        JOIN item_template it ON it.id = d.item_template_id
        JOIN category_template ct ON ct.id = it.category_id
        JOIN area_template a ON a.id = ct.area_id
        WHERE d.tenant_id = ? AND d.raised_cycle_number = 1
        AND d.unit_id IN (
            SELECT u.id FROM unit u
            WHERE u.tenant_id = ? AND u.phase_id = ? AND u.unit_type = '4-Bed'
            AND EXISTS (
                SELECT 1 FROM inspection i
                WHERE i.unit_id = u.id AND i.tenant_id = ?
                AND i.cycle_number = 1 AND i.status = 'pending_followup'
            )
        )
    """, [tenant_id, tenant_id, phase_id, tenant_id])

    # --- Map area_name -> room group (bedrooms merged) ---
    def room_group(area_name):
        if area_name and area_name.upper().startswith('BEDROOM'):
            return 'BEDROOMS'
        return area_name

    # Display order + friendly labels for the 4 groups.
    GROUP_ORDER = ['KITCHEN', 'BATHROOM', 'LOUNGE', 'BEDROOMS']
    GROUP_LABEL = {
        'KITCHEN': 'Kitchen',
        'BATHROOM': 'Bathroom',
        'LOUNGE': 'Lounge',
        'BEDROOMS': 'Bedrooms',
    }

    # --- Aggregate by logical key (group, item_description, trade) ---
    # agg[key] = {units:set, logged:int, comments:Counter}
    agg = {}
    group_units = defaultdict(set)      # distinct units affected per group
    group_logged = defaultdict(int)     # total logged per group
    proj_units = defaultdict(set)       # for project-wide top 10 (key = item/trade)
    proj_logged = defaultdict(int)
    proj_meta = {}                      # key -> (item, trade, group)

    for r in raw_rows:
        grp = room_group(r['area'])
        key = (grp, r['item'], r['trade'])
        if key not in agg:
            agg[key] = {'units': set(), 'logged': 0, 'comments': defaultdict(int)}
        agg[key]['units'].add(r['unit_id'])
        agg[key]['logged'] += 1
        agg[key]['comments'][r['cmt']] += 1

        group_units[grp].add(r['unit_id'])
        group_logged[grp] += 1

        # Project-wide: same logical item across whichever room it lives in.
        # Keyed by (item, trade) so a kitchen tap and a bathroom tap stay
        # distinct only if descriptions differ; if an identical item_description
        # spans rooms it merges project-wide (correct for a systemic view).
        pkey = (r['item'], r['trade'])
        proj_units[pkey].add(r['unit_id'])
        proj_logged[pkey] += 1
        proj_meta[pkey] = (r['item'], r['trade'], grp)

    cu = cohort_units if cohort_units > 0 else 1  # avoid div-by-zero

    def top_comments(cmt_counter, n=3):
        items = sorted(cmt_counter.items(), key=lambda kv: -kv[1])[:n]
        return [{'text': t, 'cnt': c} for t, c in items]

    # --- Build per-group top-10 lists (ranked by units-affected desc) ---
    by_group = OrderedDict()
    for grp in GROUP_ORDER:
        rows = []
        for (g, item, trade), v in agg.items():
            if g != grp:
                continue
            ua = len(v['units'])
            rows.append({
                'item': item,
                'trade': trade,
                'units': ua,
                'rate': round(ua / cu * 100),
                'logged': v['logged'],
                'comments': top_comments(v['comments']),
            })
        # Rank: units-affected desc, then logged desc as tiebreak.
        rows.sort(key=lambda x: (-x['units'], -x['logged']))
        for i, row in enumerate(rows[:10]):
            row['rank'] = i + 1
        gu = len(group_units[grp])
        by_group[grp] = {
            'key': grp,
            'label': GROUP_LABEL.get(grp, grp.title()),
            'rows': rows[:10],
            'group_units_affected': gu,
            'group_rate': round(gu / cu * 100),
            'group_logged': group_logged[grp],
            'distinct_items': len([r for r in rows]),
        }

    # --- Project-wide top 10 (ranked by units-affected desc) ---
    proj_rows = []
    for pkey, units in proj_units.items():
        ua = len(units)
        item, trade, grp = proj_meta[pkey]
        proj_rows.append({
            'item': item,
            'trade': trade,
            'group': GROUP_LABEL.get(grp, grp.title()),
            'units': ua,
            'rate': round(ua / cu * 100),
            'logged': proj_logged[pkey],
        })
    proj_rows.sort(key=lambda x: (-x['units'], -x['logged']))
    for i, row in enumerate(proj_rows[:10]):
        row['rank'] = i + 1
    project_top10 = proj_rows[:10]

    # --- Room summary tiles (exec page) ---
    room_tiles = []
    for grp in GROUP_ORDER:
        g = by_group[grp]
        room_tiles.append({
            'label': g['label'],
            'units_affected': g['group_units_affected'],
            'rate': g['group_rate'],
            'logged': g['group_logged'],
        })

    # --- Trade accountability (page 6): roll ALL C1 defects up by trade ---
    # units affected per trade = distinct units carrying >=1 defect of that trade
    # worst item = the trade's single most-widespread defect_description.
    trade_units = defaultdict(set)
    trade_logged = defaultdict(int)
    trade_items = defaultdict(set)              # distinct item_descriptions per trade
    trade_item_units = defaultdict(set)         # (trade,item) -> distinct units
    for r in raw_rows:
        tr = r['trade']
        trade_units[tr].add(r['unit_id'])
        trade_logged[tr] += 1
        trade_items[tr].add(r['item'])
        trade_item_units[(tr, r['item'])].add(r['unit_id'])

    trade_rows = []
    for tr, units in trade_units.items():
        ua = len(units)
        # worst item for this trade by units-affected
        worst_item, worst_ua = '-', -1
        for (t2, item), iu in trade_item_units.items():
            if t2 != tr:
                continue
            if len(iu) > worst_ua:
                worst_ua, worst_item = len(iu), item
        trade_rows.append({
            'trade': tr,
            'units': ua,
            'rate': round(ua / cu * 100),
            'item_count': len(trade_items[tr]),
            'logged': trade_logged[tr],
            'worst_item': worst_item,
        })
    trade_rows.sort(key=lambda x: (-x['units'], -x['logged']))
    for i, row in enumerate(trade_rows):
        row['rank'] = i + 1
    trade_accountability = trade_rows

    return {
        'cohort_units': cohort_units,
        'total_4bed_units': total_4bed_units,
        'total_defects': total_defects,
        'avg_per_unit': avg_per_unit,
        'project_top10': project_top10,
        'by_group': list(by_group.values()),
        'room_tiles': room_tiles,
        'trade_accountability': trade_accountability,
    }
