import sqlite3
conn = sqlite3.connect('/var/data/inspections.db')
cur = conn.cursor()

cur.execute('''
    SELECT u.unit_number, COUNT(*) as cnt
    FROM defect d JOIN unit u ON d.unit_id = u.id
    WHERE d.status = 'open' AND d.tenant_id = 'MONOGRAPH'
    GROUP BY u.unit_number ORDER BY u.unit_number
''')
simple = {r[0]: r[1] for r in cur.fetchall()}

cur.execute('''
    SELECT u.unit_number, COUNT(*) as cnt
    FROM defect d
    JOIN unit u ON d.unit_id = u.id
    JOIN item_template it ON d.item_template_id = it.id
    JOIN category_template ct ON it.category_id = ct.id
    JOIN area_template at ON ct.area_id = at.id
    WHERE d.raised_cycle_id = '792812c7' AND d.tenant_id = 'MONOGRAPH' AND d.status = 'open'
    GROUP BY u.unit_number ORDER BY u.unit_number
''')
joined = {r[0]: r[1] for r in cur.fetchall()}

print(f'{"Unit":<6} {"Simple":<8} {"Joined":<8} {"Match"}')
print('-' * 30)
for u in sorted(set(list(simple.keys()) + list(joined.keys()))):
    s = simple.get(u, 0)
    j = joined.get(u, 0)
    m = 'OK' if s == j else 'DIFF'
    print(f'{u:<6} {s:<8} {j:<8} {m}')

cur.execute('''
    SELECT u.unit_number, d.item_template_id, COUNT(*) as cnt
    FROM defect d JOIN unit u ON d.unit_id = u.id
    WHERE d.status = 'open' AND d.tenant_id = 'MONOGRAPH'
    GROUP BY d.unit_id, d.item_template_id HAVING COUNT(*) > 1
''')
dupes = cur.fetchall()
print(f'\nDuplicates: {len(dupes)}')
for r in dupes:
    print(f'  Unit {r[0]}: item {r[1]} x{r[2]}')
conn.close()
