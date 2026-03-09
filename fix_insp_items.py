import sqlite3, uuid
from datetime import datetime, timezone
conn = sqlite3.connect('/var/data/inspections.db')
cur = conn.cursor()
now = datetime.now(timezone.utc).isoformat()
TENANT = 'MONOGRAPH'
inspections = [('4e51fb9a','163'),('96ad4e45','164'),('1fda9d3d','165'),('ccf1b4cc','TEST-999'),('6d506393','TEST-999'),('301a7c5e','160'),('2fdfa7d4','161'),('c662bb97','162')]
deleted_templates = ['d8b18053','f0e65cf3','cba91076','9935d75a','853f0440','c3d253b5','5791354d','820b2e59']
new_op_templates = ['6a780920','c7d3ece2','fd3ca682','d45cfe75','4e9d29c5','a421d142','74797a68','24160cca','b7e9e8a3','6755790e','2e97d1b1','8bb92df0']
for iid, unit in inspections:
    for tmpl in deleted_templates:
        cur.execute('DELETE FROM inspection_item WHERE inspection_id=? AND item_template_id=?', (iid, tmpl))
    print(f'Unit {unit} ({iid}): deleted stale rows')
    added = 0
    for tmpl in new_op_templates:
        cur.execute('SELECT id FROM inspection_item WHERE inspection_id=? AND item_template_id=?', (iid, tmpl))
        if cur.fetchone():
            continue
        nid = uuid.uuid4().hex[:8]
        cur.execute('INSERT INTO inspection_item (id, tenant_id, inspection_id, item_template_id, status, marked_at) VALUES (?,?,?,?,?,?)', (nid, TENANT, iid, tmpl, 'skipped', now))
        added += 1
    print(f'Unit {unit} ({iid}): added {added} op items')
    cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=?', (iid,))
    print(f'Unit {unit} ({iid}): total = {cur.fetchone()[0]}')
conn.commit()
print('COMMITTED')
conn.close()
