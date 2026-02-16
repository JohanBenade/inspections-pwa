import sqlite3, uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

UNIT_NUMBER = '131'
INSPECTOR_ID = 'insp-006'
INSPECTOR_NAME = 'Fisokuhle Matsepe'
INSPECTION_DATE = '2026-02-13'
TENANT = 'MONOGRAPH'
CYCLE_ID = '179b2b9d'
EXCLUSION_SOURCE_CYCLE = '792812c7'

DEFECTS = [
    ('cbaefabd', 'Glass needs to be cleaned', 'NTS'),
    ('82751f2d', 'Hinges missing screw cover', 'NTS'),
    ('707304a2', 'Glass needs to be cleaned', 'NTS'),
    ('e49da716', 'Top gasket to be checked or redone', 'NTS'),
    ('6957702f', 'Inconsistent grout colour', 'NTS'),
    ('522b4aeb', 'Broken tile/cracked as indicated', 'NTS'),
    ('6957702f', 'Grout missing as indicated', 'NTS'),
    ('1664ae23', 'Skating residue to be cleaned', 'NTS'),
    ('7414ad92', 'DB is loose', 'NTS'),
    ('6b89724d', 'Fluorescent led 2x bulbs to be cleaned', 'NTS'),
    ('470a5289', 'Handles with plastic wrap', 'NTS'),
    ('9f743e7d', 'Cardboard holding top to be removed', 'NTS'),
    ('a296edd8', 'Missing screw cover', 'NTS'),
    ('e326b993', 'Damage on door behind', 'NTS'),
    ('a6939da2', 'D3 operation hard to open', 'NTS'),
    ('8d063b43', 'Hard to open below', 'NTS'),
    ('afcc1bc2', 'Paint is chipped as indicated', 'NTS'),
    ('41c9bd11', 'Broken tile as indicated by door entrance', 'NTS'),
    ('e1d9e932', 'Missing grout in between tiles by entrance', 'NTS'),
    ('7987028d', 'Door hard to close or does not close at all', 'NTS'),
    ('412e122e', 'Door cannot close without force', 'NTS'),
    ('f2df64a6', 'Have two tone colours as indicated', 'NTS'),
    ('e833bf33', 'Hinges to be repainted', 'NTS'),
    ('6624b692', 'To be cleaned as indicated', 'NTS'),
    ('e3f789d6', 'Damaged paint as indicated', 'NTS'),
    ('66cc0d36', 'Chipped at the bottom', 'NTS'),
    ('6e2d53af', 'Damaged paint as indicated', 'NTS'),
    ('6f905df9', 'Door not hitting the door stop properly', 'NTS'),
]

def gen_id(): return uuid.uuid4().hex[:8]
def now_iso(): return datetime.now(timezone.utc).isoformat()
def fuzzy_match(text, candidates, threshold=0.7):
    best_match, best_score = None, 0
    text_lower = text.lower().strip()
    for c in candidates:
        score = SequenceMatcher(None, text_lower, c.lower().strip()).ratio()
        if score > best_score: best_score = score; best_match = c
    return (best_match, best_score) if best_score >= threshold else (None, 0)
def wash_description(cur, tid, raw):
    cur.execute("SELECT ct.category_name FROM item_template it JOIN category_template ct ON it.category_id=ct.id WHERE it.id=?", (tid,))
    r = cur.fetchone(); cat = r[0] if r else 'UNKNOWN'
    cur.execute("SELECT description FROM defect_library WHERE tenant_id=? AND item_template_id=? ORDER BY usage_count DESC", (TENANT, tid))
    entries = [r[0] for r in cur.fetchall()]
    if entries:
        m, s = fuzzy_match(raw, entries)
        if m: return m, f"item-specific ({s:.2f})", cat
    cur.execute("SELECT description FROM defect_library WHERE tenant_id=? AND category_name=? AND item_template_id IS NULL ORDER BY usage_count DESC", (TENANT, cat))
    entries = [r[0] for r in cur.fetchall()]
    if entries:
        m, s = fuzzy_match(raw, entries)
        if m: return m, f"category-fallback ({s:.2f})", cat
    cleaned = raw.strip()
    if cleaned: cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned, "NEW", cat

def main():
    conn = sqlite3.connect('/var/data/inspections.db'); cur = conn.cursor(); now = now_iso()
    print(f"=== IMPORT: Unit {UNIT_NUMBER} ===\nInspector: {INSPECTOR_NAME}\nDate: {INSPECTION_DATE}\nCycle: {CYCLE_ID}\n")
    all_valid = True
    for tid, rd, dt in DEFECTS:
        cur.execute('SELECT id FROM item_template WHERE id=? AND tenant_id=?', (tid, TENANT))
        if not cur.fetchone(): print(f"  MISSING: {tid} ({rd})"); all_valid = False
    if not all_valid: print("ABORTING"); conn.close(); return
    print(f"All {len(DEFECTS)} template IDs verified\n")
    cur.execute('SELECT id FROM unit WHERE unit_number=? AND tenant_id=?', (UNIT_NUMBER, TENANT))
    row = cur.fetchone()
    if not row: print(f"ERROR: Unit {UNIT_NUMBER} not found"); conn.close(); return
    unit_id = row[0]; print(f"Unit ID: {unit_id}")
    cur.execute('SELECT id, status FROM inspection WHERE unit_id=? AND cycle_id=?', (unit_id, CYCLE_ID))
    row = cur.fetchone()
    if row:
        insp_id = row[0]
        if row[1] not in ('not_started','in_progress'): print(f"Already {row[1]}"); conn.close(); return
    else:
        insp_id = gen_id()
        cur.execute("INSERT INTO inspection (id,tenant_id,unit_id,cycle_id,inspection_date,inspector_id,inspector_name,status,started_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,'in_progress',?,?,?)",
            (insp_id, TENANT, unit_id, CYCLE_ID, INSPECTION_DATE, INSPECTOR_ID, INSPECTOR_NAME, now, now, now))
    cur.execute("UPDATE inspection SET inspector_id=?,inspector_name=?,updated_at=? WHERE id=?", (INSPECTOR_ID, INSPECTOR_NAME, now, insp_id))
    cur.execute("UPDATE cycle_unit_assignment SET inspector_id=? WHERE cycle_id=? AND unit_id=?", (INSPECTOR_ID, CYCLE_ID, unit_id))
    cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=?', (insp_id,))
    if cur.fetchone()[0] == 0:
        cur.execute('SELECT id FROM item_template WHERE tenant_id=?', (TENANT,))
        for t in cur.fetchall(): cur.execute("INSERT INTO inspection_item (id,tenant_id,inspection_id,item_template_id,status,marked_at) VALUES (?,?,?,?,'pending',NULL)", (gen_id(), TENANT, insp_id, t[0]))
        print("Created 523 inspection items")
    cur.execute("SELECT DISTINCT ii.item_template_id FROM inspection_item ii JOIN inspection i ON ii.inspection_id=i.id WHERE i.cycle_id=? AND ii.status='skipped'", (EXCLUSION_SOURCE_CYCLE,))
    excluded_ids = set(r[0] for r in cur.fetchall()); print(f"Exclusions: {len(excluded_ids)}")
    for eid in excluded_ids: cur.execute("UPDATE inspection_item SET status='skipped',marked_at=? WHERE inspection_id=? AND item_template_id=?", (now, insp_id, eid))
    clean = []
    print("\n--- EXCLUSION OVERLAP ---")
    for tid, rd, dt in DEFECTS:
        if tid in excluded_ids: print(f"  DROPPED: [{tid}] {rd}")
        else: clean.append((tid, rd, dt))
    print(f"\n--- WASH + CREATE ({len(clean)} defects) ---")
    new_lib = []; dc = 0
    for tid, rd, dt in clean:
        wd, ws, cat = wash_description(cur, tid, rd)
        if "NEW" in ws: new_lib.append((tid, cat, wd))
        print(f"  [{tid}] {rd} -> {wd} [{ws}]")
        did = gen_id(); dtype = 'not_installed' if dt=='NI' else 'not_to_standard'
        cur.execute("INSERT INTO defect (id,tenant_id,unit_id,item_template_id,raised_cycle_id,defect_type,status,original_comment,created_at,updated_at) VALUES (?,?,?,?,?,?,'open',?,?,?)",
            (did, TENANT, unit_id, tid, CYCLE_ID, dtype, wd, now, now))
        cur.execute("UPDATE inspection_item SET status=?,comment=?,marked_at=? WHERE inspection_id=? AND item_template_id=?",
            (dtype, wd, now, insp_id, tid)); dc += 1
    print(f"Defects created: {dc}")
    cur.execute("UPDATE inspection_item SET status='ok',marked_at=? WHERE inspection_id=? AND status='pending'", (now, insp_id))
    print(f"Marked OK: {cur.rowcount}")
    for tid, cat, desc in new_lib:
        cur.execute("INSERT INTO defect_library (id,tenant_id,category_name,item_template_id,description,usage_count,is_system,created_at) VALUES (?,?,?,?,?,1,0,?)",
            (gen_id(), TENANT, cat, tid, desc, now))
    if new_lib: print(f"New library entries: {len(new_lib)}")
    cur.execute("UPDATE inspection SET status='submitted',submitted_at=?,updated_at=? WHERE id=?", (now, now, insp_id))
    cur.execute("UPDATE unit SET status='in_progress' WHERE id=? AND status='not_started'", (unit_id,))
    print("\n=== VERIFICATION ===")
    for s in ['skipped','ok','not_to_standard','not_installed','pending']:
        cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=? AND status=?', (insp_id, s))
        print(f"{s}: {cur.fetchone()[0]}")
    cur.execute('SELECT COUNT(*) FROM defect WHERE unit_id=? AND raised_cycle_id=? AND status=?', (unit_id, CYCLE_ID, 'open'))
    print(f"Defects: {cur.fetchone()[0]}")
    conn.commit(); print("\nCOMMITTED SUCCESSFULLY"); conn.close()

if __name__ == '__main__': main()
