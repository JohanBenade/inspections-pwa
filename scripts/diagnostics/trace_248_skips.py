import sqlite3
c = sqlite3.connect('/var/data/inspections.db'); c.row_factory = sqlite3.Row
TID = 'MONOGRAPH'
EL = '69ce0e91'

u = c.execute("SELECT id, floor FROM unit WHERE tenant_id=? AND unit_number='248'", [TID]).fetchone()
insp = c.execute("""SELECT id, cycle_id, exclusion_list_id FROM inspection
    WHERE unit_id=? AND tenant_id=? AND cycle_number=2
    ORDER BY created_at DESC LIMIT 1""", [u['id'], TID]).fetchone()
print(f"Unit 248 floor={u['floor']}  C2 insp={insp['id']}  insp.excl={insp['exclusion_list_id']}")

# membership of list 69ce0e91
mem = set(r['item_template_id'] for r in
    c.execute("SELECT item_template_id FROM exclusion_list_item WHERE exclusion_list_id=?", [EL]))
print(f"list {EL} membership size: {len(mem)}")

# the skipped items on this inspection
sk = c.execute("""SELECT ii.item_template_id, it.item_description, it.floor_condition
    FROM inspection_item ii
    JOIN item_template it ON it.id = ii.item_template_id
    WHERE ii.inspection_id=? AND ii.status='skipped'
    ORDER BY it.item_description""", [insp['id']]).fetchall()
print(f"\nskipped items: {len(sk)}")
for s in sk:
    in_list = s['item_template_id'] in mem
    print(f"  - {s['item_description'][:45]:45} | floor_cond={s['floor_condition']:12} | in_list={in_list}")

# how many list members are 4-Bed-applicable / would even exist as items here
present = c.execute("""SELECT COUNT(*) n FROM inspection_item ii
    WHERE ii.inspection_id=? AND ii.item_template_id IN
    (SELECT item_template_id FROM exclusion_list_item WHERE exclusion_list_id=?)""",
    [insp['id'], EL]).fetchone()['n']
print(f"\nlist members present as items on this inspection: {present} of {len(mem)}")
