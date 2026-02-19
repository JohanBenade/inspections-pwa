import sqlite3

conn = sqlite3.connect('/var/data/inspections.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print('=' * 80)
print('TEMPLATE HIERARCHY')
print('=' * 80)
cur.execute('''
    SELECT at.area_name, ct.category_name, it.id as item_id, it.item_description
    FROM item_template it
    JOIN category_template ct ON it.category_id = ct.id
    JOIN area_template at ON ct.area_id = at.id
    WHERE it.tenant_id = 'MONOGRAPH'
    ORDER BY at.area_name, ct.category_name, it.item_description
''')
rows = [dict(r) for r in cur.fetchall()]
ca = cc = None
for r in rows:
    if r['area_name'] != ca:
        ca = r['area_name']
        print(f"\n### {ca}")
    if r['category_name'] != cc:
        cc = r['category_name']
        print(f"  {cc}")
    print(f"    {r['item_id']} | {r['item_description']}")

print('\n' + '=' * 80)
print('EXCLUDED TEMPLATE IDs (cycle 36e85327)')
print('=' * 80)
cur.execute('''
    SELECT DISTINCT ii.item_template_id, it.item_description, ct.category_name, at.area_name
    FROM inspection_item ii
    JOIN inspection i ON ii.inspection_id = i.id
    JOIN item_template it ON ii.item_template_id = it.id
    JOIN category_template ct ON it.category_id = ct.id
    JOIN area_template at ON ct.area_id = at.id
    WHERE i.cycle_id = '36e85327' AND ii.status = 'skipped'
    ORDER BY at.area_name, ct.category_name
''')
for r in cur.fetchall():
    r = dict(r)
    print(f"  {r['item_template_id']} | {r['area_name']} > {r['category_name']} > {r['item_description']}")

print('\n' + '=' * 80)
print('DEFECT LIBRARY (top 50 item-specific)')
print('=' * 80)
cur.execute('''
    SELECT dl.item_template_id, dl.description, dl.usage_count, at.area_name, it.item_description
    FROM defect_library dl
    LEFT JOIN item_template it ON dl.item_template_id = it.id
    LEFT JOIN category_template ct ON it.category_id = ct.id
    LEFT JOIN area_template at ON ct.area_id = at.id
    WHERE dl.tenant_id = 'MONOGRAPH' AND dl.item_template_id IS NOT NULL
    ORDER BY dl.usage_count DESC LIMIT 50
''')
for r in cur.fetchall():
    r = dict(r)
    print(f"  [{r['usage_count']:3d}x] {r['item_template_id']} | {r['area_name']} > {r['item_description']} | {r['description']}")

print('\n' + '=' * 80)
print('UNIT STATUS')
print('=' * 80)
for unum in ['029','030','046','054','055','056']:
    cur.execute("SELECT id, block, floor, status FROM unit WHERE unit_number=? AND tenant_id='MONOGRAPH'", (unum,))
    u = cur.fetchone()
    if u:
        u = dict(u)
        cur.execute("SELECT id, cycle_id, status FROM inspection WHERE unit_id=? AND tenant_id='MONOGRAPH'", (u['id'],))
        insps = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT COUNT(*) as c FROM defect WHERE unit_id=? AND status='open'", (u['id'],))
        dc = cur.fetchone()[0]
        print(f"  {unum}: id={u['id']} B{u['block']}F{u['floor']} status={u['status']} | {len(insps)} insp | {dc} defects")
        for i in insps:
            print(f"    insp={i['id']} cycle={i['cycle_id']} status={i['status']}")
    else:
        print(f"  {unum}: NOT FOUND")

print('\n' + '=' * 80)
print('INSPECTOR CHECK')
print('=' * 80)
cur.execute("SELECT id, name, login_code, role FROM inspector WHERE tenant_id='MONOGRAPH' AND name LIKE '%Thembinkosi%'")
insp = cur.fetchall()
if insp:
    for r in insp:
        r = dict(r)
        print(f"  {r['id']} | {r['name']} | {r['login_code']} | {r['role']}")
else:
    print('  NOT FOUND')
    cur.execute("SELECT id, name, login_code FROM inspector WHERE tenant_id='MONOGRAPH' AND role='inspector'")
    for r in cur.fetchall():
        r = dict(r)
        print(f"  existing: {r['id']} | {r['name']} | {r['login_code']}")

conn.close()
