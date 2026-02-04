import sqlite3, uuid

def gen_id():
    return uuid.uuid4().hex[:8]

conn = sqlite3.connect('/var/data/inspections.db')
cur = conn.cursor()

UNIT_NUMBER = '028'
INSPECTOR_ID = 'team-lead'
INSPECTOR_NAME = 'Alex Nataniel'
CYCLE_ID = '792812c7'
TENANT = 'MONOGRAPH'

cur.execute("SELECT id FROM unit WHERE unit_number = ? AND tenant_id = ?", [UNIT_NUMBER, TENANT])
row = cur.fetchone()
if not row:
    print("ERROR: Unit 028 not found!")
    conn.close()
    exit()
unit_id = row[0]
print(f"Unit 028 ID: {unit_id}")

cur.execute("SELECT id FROM inspection WHERE unit_id = ?", [unit_id])
existing = cur.fetchone()
if existing:
    old_id = existing[0]
    cur.execute("DELETE FROM defect WHERE unit_id = ?", [unit_id])
    print(f"  Cleaned {cur.rowcount} old defects")
    cur.execute("DELETE FROM inspection_item WHERE inspection_id = ?", [old_id])
    print(f"  Cleaned {cur.rowcount} old items")
    cur.execute("DELETE FROM inspection WHERE id = ?", [old_id])
    print(f"  Cleaned old inspection {old_id}")
    conn.commit()

cur.execute("SELECT item_template_id FROM cycle_excluded_item WHERE cycle_id = ?", [CYCLE_ID])
excluded_ids = set(r[0] for r in cur.fetchall())
print(f"Exclusions: {len(excluded_ids)}")

inspection_id = gen_id()
cur.execute("""INSERT INTO inspection 
    (id, tenant_id, unit_id, cycle_id, inspection_date, inspector_id, inspector_name, status, created_at)
    VALUES (?, ?, ?, ?, '2026-01-27', ?, ?, 'in_progress', CURRENT_TIMESTAMP)""",
    [inspection_id, TENANT, unit_id, CYCLE_ID, INSPECTOR_ID, INSPECTOR_NAME])

cur.execute("SELECT id FROM item_template WHERE tenant_id = ?", [TENANT])
templates = cur.fetchall()
sk = 0
pn = 0
for (tid,) in templates:
    s = 'skipped' if tid in excluded_ids else 'pending'
    if s == 'skipped': sk += 1
    else: pn += 1
    cur.execute("INSERT INTO inspection_item (id,tenant_id,inspection_id,item_template_id,status,created_at) VALUES (?,'MONOGRAPH',?,?,?,CURRENT_TIMESTAMP)",
        [gen_id(), inspection_id, tid, s])
print(f"Inspection {inspection_id}: {sk} skipped, {pn} pending")

defects = [
    ("c897b472","Paint is damaged as indicated"),
    ("244e8c43","Thumb turn not installed"),
    ("244e8c43","Lock is recessed into door"),
    ("e4bb8e59","Tile into window sill does not align with tile trim"),
    ("828b90e9","Inconsistent grout colour"),
    ("707304a2","Glass needs to be cleaned"),
    ("6957702f","Inconsistent grout colour"),
    ("3cf49a3d","Grout missing between tile skirting and floor"),
    ("117c2748","Layout not as per drawing"),
    ("5158daf4","Carcass back wall needs to be painted"),
    ("255488c3","Hinges look water damaged"),
    ("624544cd","Carcass has mould"),
    ("28814cf6","Finish on handle is scratched"),
    ("09e5b0d4","Fixing to wall not done well"),
    ("5fe88982","Leg support is loose"),
    ("76718e79","Gap between counter top and B.I.C"),
    ("8ada7164","Damaged finish as indicated"),
    ("c248c406","Orchid bay paint has chipped plaster above plug point"),
    ("feafbe9d","Grout has inconsistent colour"),
    ("04796e27","Paint is damaged as indicated"),
    ("afcc1bc2","Paint is damaged as indicated"),
    ("a1eecb62","Paint overlaps near window"),
    ("a1eecb62","Unpainted patch under study desk"),
    ("db6da547","Frame has paint marks"),
    ("5be0243e","Gasket has gaps on the edges"),
    ("5d02b531","Window is difficult to close"),
    ("41c9bd11","Tile is missing behind the door"),
    ("14eb7511","Gap between tile skirting and floor as indicated"),
    ("a7d14262","Damaged paint near light switch as indicated"),
    ("09b9fc9b","Handles are missing screw covers"),
    ("a7f0db32","Hinges installed causing door not to be flushed"),
    ("80177e8e","Has paint marks"),
    ("6624b692","Plaster damaged near WIFI cable entry point"),
    ("6579fac6","Damaged paint as indicated"),
    ("035a042f","Hinges installed causing door not to be flushed"),
    ("212d83e1","Has paint marks"),
    ("66cc0d36","Damaged paint as indicated"),
    ("6f905df9","Door stop is loose"),
    ("248d3871","White paint marks as indicated"),
    ("1fb635e9","Glass needs to be cleaned"),
    ("b41bf52d","Damaged plaster above the window"),
    ("b6b5d166","Has inconsistent paint application"),
    ("e326b993","Paint is damaged as indicated"),
    ("f27ee884","Hinges need to be repainted"),
    ("ebb584a4","Handle has no screws to door"),
    ("76c93f42","Tile into window sill has a large gap to window"),
    ("f1438790","Missing grout as indicated"),
    ("acf61869","Poor plaster work above window"),
    ("8fa8781c","Inconsistent grout colour"),
    ("8667f32c","Not flushed to wall"),
]

print(f"Processing {len(defects)} defects...")

cm = {}
for tid, c in defects:
    if tid not in cm: cm[tid] = []
    cm[tid].append(c)

nts = 0
for tid, comments in cm.items():
    cur.execute("UPDATE inspection_item SET status='not_to_standard', comment=?, updated_at=CURRENT_TIMESTAMP WHERE inspection_id=? AND item_template_id=?",
        ["; ".join(comments), inspection_id, tid])
    if cur.rowcount > 0: nts += 1
    else: print(f"  WARNING: missing {tid}")

for tid, comment in defects:
    cur.execute("INSERT INTO defect (id,tenant_id,unit_id,item_template_id,raised_cycle_id,defect_type,status,original_comment,created_at,updated_at) VALUES (?,'MONOGRAPH',?,?,?,'not_to_standard','open',?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",
        [gen_id(), unit_id, tid, CYCLE_ID, comment])

cur.execute("UPDATE inspection_item SET status='ok', updated_at=CURRENT_TIMESTAMP WHERE inspection_id=? AND status='pending'", [inspection_id])
ok = cur.rowcount
cur.execute("UPDATE inspection SET status='submitted', submitted_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE id=?", [inspection_id])
cur.execute("UPDATE unit SET status='in_progress' WHERE id=?", [unit_id])
conn.commit()

print(f"\n=== UNIT 028 DONE ===")
print(f"Inspection: {inspection_id}")
print(f"NTS: {nts} | OK: {ok} | Defects: {len(defects)}")
cur.execute("SELECT status, COUNT(*) FROM inspection_item WHERE inspection_id=? GROUP BY status", [inspection_id])
for r in cur.fetchall(): print(f"  {r[0]}: {r[1]}")
cur.execute("SELECT at.area_name, COUNT(*) FROM defect d JOIN item_template it ON d.item_template_id=it.id JOIN category_template ct ON it.category_id=ct.id JOIN area_template at ON ct.area_id=at.id WHERE d.unit_id=? AND d.status='open' GROUP BY at.area_name ORDER BY at.area_name", [unit_id])
print("Defects by area:")
for r in cur.fetchall(): print(f"  {r[0]}: {r[1]}")
conn.close()
