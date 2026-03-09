import sqlite3, uuid
from datetime import datetime, timezone

conn = sqlite3.connect('/var/data/inspections.db')
cur = conn.cursor()
now = datetime.now(timezone.utc).isoformat()

TENANT = 'MONOGRAPH'

renames = [
    ('554d76c3', 'panel heater plug wall 01 - installation', 4),
    ('1aeff3ea', 'double light switch on wall 02 - installation', 6),
    ('28999baf', 'combination plug wall 03 - installation', 8),
    ('a11aff40', 'panel heater plug wall 07 - installation', 4),
    ('de73d950', 'double light switch on wall 08 - installation', 6),
    ('a21624c2', 'combination plug wall 05 - installation', 8),
    ('ef4935cb', 'panel heater plug wall 21 - installation', 4),
    ('c57a6bb2', 'double light switch on wall 24 - installation', 6),
    ('5cee2550', 'combination plug wall 22 - installation', 8),
    ('700c338e', 'panel heater plug wall 20 - installation', 4),
    ('5b96638f', 'double light switch on wall 17 - installation', 6),
    ('afe6b938', 'combination plug wall 19 - installation', 8),
]
for rid, new_name, new_order in renames:
    cur.execute('UPDATE item_template SET item_description=?, item_order=? WHERE id=?', (new_name, new_order, rid))
    print(f'Renamed: {rid} -> {new_name}')

old_children = ['d8b18053','f0e65cf3','cba91076','9935d75a','853f0440','c3d253b5','5791354d','820b2e59']
for cid in old_children:
    cur.execute('DELETE FROM item_template WHERE id=?', (cid,))
    print(f'Deleted: {cid}')

cur.execute('''SELECT ct.id, at.area_name FROM category_template ct
    JOIN area_template at ON ct.area_id = at.id
    WHERE ct.tenant_id=? AND ct.category_name="ELECTRICAL" AND at.area_name LIKE "BEDROOM%"
    ORDER BY at.area_name''', (TENANT,))
cats = {row[1]: row[0] for row in cur.fetchall()}

cur.execute('''SELECT it.parent_item_id, at.area_name FROM item_template it
    JOIN category_template ct ON it.category_id = ct.id
    JOIN area_template at ON ct.area_id = at.id
    WHERE it.tenant_id=? AND ct.category_name="ELECTRICAL"
    AND at.area_name LIKE "BEDROOM%" AND it.depth=1
    GROUP BY at.area_name''', (TENANT,))
parents = {row[1]: row[0] for row in cur.fetchall()}

new_items = [
    ('BEDROOM A','panel heater plug wall 01 - operation',5),
    ('BEDROOM A','double light switch on wall 02 - operation',7),
    ('BEDROOM A','combination plug wall 03 - operation',9),
    ('BEDROOM B','panel heater plug wall 07 - operation',5),
    ('BEDROOM B','double light switch on wall 08 - operation',7),
    ('BEDROOM B','combination plug wall 05 - operation',9),
    ('BEDROOM C','panel heater plug wall 21 - operation',5),
    ('BEDROOM C','double light switch on wall 24 - operation',7),
    ('BEDROOM C','combination plug wall 22 - operation',9),
    ('BEDROOM D','panel heater plug wall 20 - operation',5),
    ('BEDROOM D','double light switch on wall 17 - operation',7),
    ('BEDROOM D','combination plug wall 19 - operation',9),
]
new_ids = []
for area, desc, order in new_items:
    nid = uuid.uuid4().hex[:8]
    cur.execute('''INSERT INTO item_template
        (id, tenant_id, category_id, item_description, parent_item_id, depth, item_order, is_active, floor_condition)
        VALUES (?,?,?,?,?,1,?,1,'all')''',
        (nid, TENANT, cats[area], desc, parents[area], order))
    new_ids.append((area, desc, nid))
    print(f'Added: {nid} [{area}] {desc}')

conn.commit()
print()
print('=== NEW OPERATION IDs ===')
for area, desc, nid in new_ids:
    print(f'{nid}  {area}  {desc}')
print('COMMITTED')
conn.close()
