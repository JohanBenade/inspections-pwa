import sqlite3, uuid
from datetime import datetime, timezone

conn = sqlite3.connect('/var/data/inspections.db')
cur = conn.cursor()
now = datetime.now(timezone.utc).isoformat()

def gen_id():
    return uuid.uuid4().hex[:8]

TENANT = 'MONOGRAPH'

items_153 = [
    '04bf84d7','063bf215','06d31697','070c65ca','078888d2','0938885b','0a8a0ca3',
    '1161cc67','13651c86','151d2b2e','1e45af79','1f2fe184','20208261','205e2898',
    '207492fc','22b679a0','244e8c43','2bd8271a','2cd5bdf0','2e14552f','30b99922',
    '31f0f475','34ea5535','35352a04','387c838c','412e4292','432df076','4538a0a8',
    '4670863e','46c2267f','4c0f7fbe','4c301408','4e025b9c','52d96bc1','5521401d',
    '5c4e84c6','5d45a701','62313ad1','663cc471','68ad5ceb','69c1cf1c','6a8feed6',
    '6c44b28e','6f7226bd','73971770','74fef16f','7b044b27','7b76217f','7d1f2e4f',
    '7d7e29c6','84795b32','874c7df6','927c1174','9359dd96','936a5aec','96baddae',
    '9720e6ac','97cdacb1','9da629f0','9f1eb7ce','a1515443','a709718f','aae98150',
    'ac6bfae8','ad6e4d5b','afa84132','b131f27e','b23f9c15','b3d74254','b4a7d129',
    'b7926d75','bb4b4360','be712f2a','bea2b10f','c4348cc6','cc84d464','cea16d6c',
    'd0262104','d149df25','d1d59d05','d21c5759','d4aab9e1','d7c9d133','d81f99e9',
    'd959dbdc','dfcb88ce','e3f789d6','ecb87392','f3c554ab','fcdb7c4f','fda2e356',
    'fe1f4b2d','ff57e58c'
]

items_159 = [x for x in items_153 if x != '74fef16f']

# Get inspection IDs
cur.execute("""SELECT i.id FROM inspection i JOIN unit u ON i.unit_id=u.id
    WHERE u.unit_number='153' AND u.tenant_id=? AND i.cycle_id='213a746f'""", (TENANT,))
insp_153 = cur.fetchone()[0]

cur.execute("""SELECT i.id FROM inspection i JOIN unit u ON i.unit_id=u.id
    WHERE u.unit_number='159' AND u.tenant_id=? AND i.cycle_id='213a746f'""", (TENANT,))
insp_159 = cur.fetchone()[0]

print(f'Inspection 153: {insp_153}')
print(f'Inspection 159: {insp_159}')

# Create 93-item list for unit 153
list_153_id = gen_id()
cur.execute("""INSERT INTO exclusion_list
    (id,tenant_id,name,description,item_count,is_active,created_by,created_at,updated_at)
    VALUES (?,?,?,?,?,1,?,?,?)""",
    (list_153_id, TENANT,
     'B6 1st Floor C1 — 93 items — v1',
     'Retroactive — actual skipped items from Unit 153 import',
     93, 'admin', now, now))
for tmpl_id in items_153:
    cur.execute("""INSERT INTO exclusion_list_item
        (id,tenant_id,exclusion_list_id,item_template_id,reason,created_at)
        VALUES (?,?,?,?,?,?)""",
        (gen_id(), TENANT, list_153_id, tmpl_id, 'retroactive', now))
cur.execute("UPDATE inspection SET exclusion_list_id=?, updated_at=? WHERE id=?",
    (list_153_id, now, insp_153))
cur.execute("""UPDATE batch_unit SET exclusion_list_id=?
    WHERE unit_id=(SELECT unit_id FROM inspection WHERE id=?)
    AND batch_id='719a38e6'""", (list_153_id, insp_153))
print(f'List 153: {list_153_id} — 93 items — assigned to {insp_153}')

# Create 92-item list for unit 159
list_159_id = gen_id()
cur.execute("""INSERT INTO exclusion_list
    (id,tenant_id,name,description,item_count,is_active,created_by,created_at,updated_at)
    VALUES (?,?,?,?,?,1,?,?,?)""",
    (list_159_id, TENANT,
     'B6 1st Floor C1 — 92 items — v1',
     'Retroactive — actual skipped items from Unit 159 import',
     92, 'admin', now, now))
for tmpl_id in items_159:
    cur.execute("""INSERT INTO exclusion_list_item
        (id,tenant_id,exclusion_list_id,item_template_id,reason,created_at)
        VALUES (?,?,?,?,?,?)""",
        (gen_id(), TENANT, list_159_id, tmpl_id, 'retroactive', now))
cur.execute("UPDATE inspection SET exclusion_list_id=?, updated_at=? WHERE id=?",
    (list_159_id, now, insp_159))
cur.execute("""UPDATE batch_unit SET exclusion_list_id=?
    WHERE unit_id=(SELECT unit_id FROM inspection WHERE id=?)
    AND batch_id='719a38e6'""", (list_159_id, insp_159))
print(f'List 159: {list_159_id} — 92 items — assigned to {insp_159}')

conn.commit()
print('COMMITTED')
conn.close()
