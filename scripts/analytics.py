import sqlite3
conn = sqlite3.connect('/var/data/inspections.db')
cur = conn.cursor()

print('=== 1. DEFECTS BY AREA (ALL UNITS) ===')
cur.execute('''
    SELECT at.area_name, COUNT(*) as cnt,
           ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM defect WHERE status='open' AND tenant_id='MONOGRAPH'), 1) as pct
    FROM defect d
    JOIN item_template it ON d.item_template_id = it.id
    JOIN category_template ct ON it.category_id = ct.id
    JOIN area_template at ON ct.area_id = at.id
    WHERE d.status='open' AND d.tenant_id='MONOGRAPH'
    GROUP BY at.area_name
    ORDER BY cnt DESC
''')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]} ({row[2]}%)')

print()
print('=== 2. DEFECTS BY CATEGORY (TOP 15) ===')
cur.execute('''
    SELECT ct.category_name, COUNT(*) as cnt
    FROM defect d
    JOIN item_template it ON d.item_template_id = it.id
    JOIN category_template ct ON it.category_id = ct.id
    WHERE d.status='open' AND d.tenant_id='MONOGRAPH'
    GROUP BY ct.category_name
    ORDER BY cnt DESC
    LIMIT 15
''')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}')

print()
print('=== 3. MOST COMMON DEFECT ITEMS (TOP 15) ===')
cur.execute('''
    SELECT at.area_name, ct.category_name, it.item_description,
           COALESCE(pit.item_description,'') as parent,
           COUNT(*) as cnt
    FROM defect d
    JOIN item_template it ON d.item_template_id = it.id
    JOIN category_template ct ON it.category_id = ct.id
    JOIN area_template at ON ct.area_id = at.id
    LEFT JOIN item_template pit ON it.parent_item_id = pit.id
    WHERE d.status='open' AND d.tenant_id='MONOGRAPH'
    GROUP BY d.item_template_id
    ORDER BY cnt DESC
    LIMIT 15
''')
for row in cur.fetchall():
    parent = f'{row[3]} > ' if row[3] else ''
    print(f'  {row[4]}x | {row[0]} > {row[1]} > {parent}{row[2]}')

print()
print('=== 4. UNITS RANKED BY DEFECT COUNT ===')
cur.execute('''
    SELECT u.unit_number, COUNT(*) as cnt, i.inspector_name
    FROM defect d
    JOIN unit u ON d.unit_id = u.id
    JOIN inspection i ON i.unit_id = u.id AND i.cycle_id = d.raised_cycle_id
    WHERE d.status='open' AND d.tenant_id='MONOGRAPH'
    GROUP BY u.unit_number
    ORDER BY cnt DESC
''')
for row in cur.fetchall():
    print(f'  Unit {row[0]}: {row[1]} defects ({row[2]})')

print()
print('=== 5. INSPECTOR STATS ===')
cur.execute('''
    SELECT i.inspector_name, COUNT(DISTINCT u.unit_number) as units,
           COUNT(d.id) as total_defects,
           ROUND(COUNT(d.id) * 1.0 / COUNT(DISTINCT u.unit_number), 1) as avg_per_unit
    FROM inspection i
    JOIN unit u ON i.unit_id = u.id
    LEFT JOIN defect d ON d.unit_id = u.id AND d.status='open'
    WHERE i.tenant_id='MONOGRAPH'
    GROUP BY i.inspector_name
    ORDER BY avg_per_unit DESC
''')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]} units, {row[2]} defects, avg {row[3]}/unit')

print()
print('=== 6. AREA x UNIT HEATMAP ===')
cur.execute('''
    SELECT u.unit_number, at.area_name, COUNT(*) as cnt
    FROM defect d
    JOIN unit u ON d.unit_id = u.id
    JOIN item_template it ON d.item_template_id = it.id
    JOIN category_template ct ON it.category_id = ct.id
    JOIN area_template at ON ct.area_id = at.id
    WHERE d.status='open' AND d.tenant_id='MONOGRAPH'
    GROUP BY u.unit_number, at.area_name
    ORDER BY u.unit_number, at.area_name
''')
heatmap = {}
areas = set()
for row in cur.fetchall():
    unit = row[0]
    area = row[1]
    areas.add(area)
    if unit not in heatmap:
        heatmap[unit] = {}
    heatmap[unit][area] = row[2]
areas = sorted(areas)
header = 'UNIT  | ' + ' | '.join(f'{a[:5]:>5}' for a in areas) + ' | TOTAL'
print(f'  {header}')
print(f'  {"-" * len(header)}')
for unit in sorted(heatmap.keys()):
    vals = [heatmap[unit].get(a, 0) for a in areas]
    row_str = f'  {unit}   | ' + ' | '.join(f'{v:>5}' for v in vals) + f' | {sum(vals):>5}'
    print(row_str)

print()
print('=== 7. DEFECT TYPE SPLIT ===')
cur.execute('''
    SELECT defect_type, COUNT(*) FROM defect
    WHERE status='open' AND tenant_id='MONOGRAPH'
    GROUP BY defect_type
''')
for row in cur.fetchall():
    print(f'  {row[0]}: {row[1]}')

print()
print('=== 8. RECURRING DEFECTS (3+ times) ===')
cur.execute('''
    SELECT original_comment, COUNT(*) as cnt
    FROM defect
    WHERE status='open' AND tenant_id='MONOGRAPH'
    GROUP BY original_comment
    HAVING cnt >= 3
    ORDER BY cnt DESC
''')
for row in cur.fetchall():
    print(f'  {row[1]}x | {row[0][:80]}')

conn.close()
