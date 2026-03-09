import sqlite3
import uuid
from datetime import datetime, timezone

conn = sqlite3.connect('/var/data/inspections.db')
cur = conn.cursor()
now = datetime.now(timezone.utc).isoformat()

def gen_id():
    return uuid.uuid4().hex[:8]

TENANT = 'MONOGRAPH'

print("=== STEP 1: MIGRATE DEFECTS ===")
defect_migrations = [
    ('e93ed50c', 'e6f434e1'),
    ('16f6a617', 'e6f434e1'),
    ('6f8db657', '522b4aeb'),
    ('efc448fd', '05c84b01'),
    ('f91d99c1', '05c84b01'),
    ('59febccf', '41c9bd11'),
    ('5a896de2', '6a0771ae'),
]
for defect_id, new_template_id in defect_migrations:
    cur.execute("UPDATE defect SET item_template_id=?, updated_at=? WHERE id=?", (new_template_id, now, defect_id))
    print(f"  Migrated defect {defect_id} -> {new_template_id} (rows={cur.rowcount})")

print()
print("=== STEP 2: CEILING DEFECT -> CATEGORY COMMENT ===")
cur.execute("SELECT id FROM unit WHERE unit_number='154' AND tenant_id=?", (TENANT,))
unit_154 = cur.fetchone()[0]
print(f"  Unit 154 id: {unit_154}")
cur.execute("""
    SELECT ct.id FROM category_template ct
    JOIN area_template at ON ct.area_id = at.id
    WHERE ct.category_name='CEILING' AND at.area_name='BEDROOM D' AND ct.tenant_id=?
""", (TENANT,))
cat_ceiling_d = cur.fetchone()[0]
print(f"  BEDROOM D CEILING category_template_id: {cat_ceiling_d}")
cycle_id = '213a746f'
cur.execute("SELECT id FROM category_comment WHERE unit_id=? AND category_template_id=? AND raised_cycle_id=? AND tenant_id=?", (unit_154, cat_ceiling_d, cycle_id, TENANT))
existing_cc = cur.fetchone()
if existing_cc:
    cc_id = existing_cc[0]
    print(f"  Existing category_comment: {cc_id}")
else:
    cc_id = gen_id()
    cur.execute("INSERT INTO category_comment (id, tenant_id, unit_id, category_template_id, raised_cycle_id, status, created_at, updated_at) VALUES (?,?,?,?,?,'open',?,?)", (cc_id, TENANT, unit_154, cat_ceiling_d, cycle_id, now, now))
    print(f"  Created category_comment: {cc_id}")
hist_id = gen_id()
cur.execute("INSERT INTO category_comment_history (id, tenant_id, category_comment_id, cycle_id, comment, status) VALUES (?,?,?,?,?,'open')", (hist_id, TENANT, cc_id, cycle_id, 'Hanging pipe on ceiling'))
print(f"  Added history: {hist_id}")
cur.execute("DELETE FROM defect WHERE id='576678ad'")
print(f"  Deleted defect 576678ad (rows={cur.rowcount})")

print()
print("=== STEP 3: RE-PARENT CHILDREN ===")
dup_ids = ['d13897d2','afc801a3','f27f045d','f3d729dd','4a540031','76ec5f36','028e00cc',
           '89cbfb2d','5750f12e','d34e733d','35a6f874','3bf9452f','30b99922','8911e60e',
           '68d3f5a4','9ade6ac4','1da94647','44757b47','d465faeb','044fd7da','1664ae23',
           '87ab7b78','7189c160','6b92618a','af45d458']
ph = ','.join('?' * len(dup_ids))
total_reparented = 0
for pid in dup_ids:
    cur.execute("UPDATE item_template SET parent_item_id=NULL, depth=0 WHERE parent_item_id=? AND tenant_id=?", (pid, TENANT))
    total_reparented += cur.rowcount
print(f"  Re-parented children: {total_reparented}")

print()
print("=== STEP 4: DELETE INSPECTION_ITEMS ===")
cur.execute(f"SELECT COUNT(*) FROM inspection_item WHERE item_template_id IN ({ph})", dup_ids)
print(f"  Rows to delete: {cur.fetchone()[0]}")
cur.execute(f"DELETE FROM inspection_item WHERE item_template_id IN ({ph})", dup_ids)
print(f"  Deleted: {cur.rowcount}")

print()
print("=== STEP 5: DELETE EXCLUSION REFERENCES ===")
cur.execute(f"DELETE FROM exclusion_list_item WHERE item_template_id IN ({ph})", dup_ids)
print(f"  exclusion_list_item deleted: {cur.rowcount}")
cur.execute(f"DELETE FROM cycle_excluded_item WHERE item_template_id IN ({ph})", dup_ids)
print(f"  cycle_excluded_item deleted: {cur.rowcount}")

print()
print("=== STEP 6: DELETE 25 DUPLICATE PARENT TEMPLATES ===")
cur.execute(f"DELETE FROM item_template WHERE id IN ({ph})", dup_ids)
print(f"  item_template deleted: {cur.rowcount}")

print()
print("=== STEP 7: VERIFY ===")
cur.execute(f"SELECT COUNT(*) FROM defect WHERE item_template_id IN ({ph})", dup_ids)
print(f"  Defects still on deleted templates: {cur.fetchone()[0]} (expected 0)")
cur.execute(f"SELECT COUNT(*) FROM item_template WHERE parent_item_id IN ({ph})", dup_ids)
print(f"  Children still pointing to deleted parents: {cur.fetchone()[0]} (expected 0)")

conn.commit()
print()
print("COMMITTED")
conn.close()
