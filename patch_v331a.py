"""
patch_v331a.py - extend _build_pipeline_report_data with cert_zone_grid

Adds certified-units-per-zone data using v330 union definition
(_formal_certified_ids | _handover_ready_ids). Same definition as the
Page 1 CERTIFIED KPI - internal consistency guaranteed.

Two edits in one logical change:
  1. Insert cert_zone_grid construction after the existing zone_grid block
  2. Add 'cert_zone_grid': cert_zone_grid to the function's return dict

Run:  python3 patch_v331a.py
"""

PATH = 'app/routes/analytics.py'

with open(PATH, 'r') as f:
    content = f.read()

# --- EDIT 1: insert cert_zone_grid block after existing zone_grid ---
OLD_1 = """    zone_grid = {
        'blocks': all_blocks,
        'floors': all_floors,
        'data': zone_map,
        'project_avg': project_avg,
    }

    # Floor label helper"""

NEW_1 = """    zone_grid = {
        'blocks': all_blocks,
        'floors': all_floors,
        'data': zone_map,
        'project_avg': project_avg,
    }

    # v331: cert_zone_grid - certified units per (block, floor)
    # Reuses v330 union: _formal_certified_ids | _handover_ready_ids
    _certified_ids = _formal_certified_ids | _handover_ready_ids
    cert_zone_map = {}
    for _u in all_units:
        _key = (_u['block'], _u['floor'])
        if _key not in cert_zone_map:
            cert_zone_map[_key] = {
                'total_units': 0,
                'certified_count': 0,
                'certified_unit_numbers': [],
            }
        cert_zone_map[_key]['total_units'] += 1
        if _u['id'] in _certified_ids:
            cert_zone_map[_key]['certified_count'] += 1
            cert_zone_map[_key]['certified_unit_numbers'].append(_u['unit_number'])

    def _collapse_unit_ranges(unit_numbers):
        if not unit_numbers:
            return ''
        nums = sorted(int(n) for n in unit_numbers)
        parts, start, prev = [], nums[0], nums[0]
        for n in nums[1:]:
            if n == prev + 1:
                prev = n
            else:
                parts.append('{:03d}'.format(start) if start == prev else '{:03d}-{:03d}'.format(start, prev))
                start = prev = n
        parts.append('{:03d}'.format(start) if start == prev else '{:03d}-{:03d}'.format(start, prev))
        return ', '.join(parts)

    for _cell in cert_zone_map.values():
        _n = _cell['total_units']
        _x = _cell['certified_count']
        _cell['certified_pct'] = round(100 * _x / _n, 1) if _n > 0 else 0
        _cell['certified_units_display'] = _collapse_unit_ranges(_cell['certified_unit_numbers'])
        if _x == 0:
            _cell['cert_stage'] = 'none'
        elif _x == _n:
            _cell['cert_stage'] = 'all'
        else:
            _cell['cert_stage'] = 'partial'

    cert_zone_grid = {
        'blocks': all_blocks,
        'floors': all_floors,
        'data': cert_zone_map,
    }

    # Floor label helper"""

assert OLD_1 in content, "EDIT 1 anchor not found in analytics.py"
assert content.count(OLD_1) == 1, "EDIT 1 anchor not unique"
content = content.replace(OLD_1, NEW_1)

# --- EDIT 2: add cert_zone_grid to return dict ---
OLD_2 = "        'zone_grid': zone_grid,"
NEW_2 = "        'zone_grid': zone_grid,\n        'cert_zone_grid': cert_zone_grid,"

assert OLD_2 in content, "EDIT 2 anchor not found in analytics.py"
assert content.count(OLD_2) == 1, "EDIT 2 anchor not unique (multiple 'zone_grid': zone_grid lines)"
content = content.replace(OLD_2, NEW_2)

with open(PATH, 'w') as f:
    f.write(content)

print("v331a applied:")
print("  - cert_zone_grid construction inserted after zone_grid block")
print("  - cert_zone_grid added to return dict")
print("")
print("Verify:")
print("  grep -n 'cert_zone_grid' app/routes/analytics.py")
