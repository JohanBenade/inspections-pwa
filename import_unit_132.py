import sqlite3, uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

UNIT_NUMBER = '132'
INSPECTOR_ID = 'insp-006'
INSPECTOR_NAME = 'Fisokuhle Matsepe'
INSPECTION_DATE = '2026-02-12'
TENANT = 'MONOGRAPH'
CYCLE_ID = '179b2b9d'
EXCLUSION_SOURCE_CYCLE = '792812c7'

DEFECTS = [
    # KITCHEN (Door/Frame/Ironmongery dropped = front door)
    ('e4bb8e59', 'Tile into window sill has hole in grout', 'NTS'),
    ('2aefb106', 'Chipped tile as indicated', 'NTS'),
    ('0740d3f1', 'Gaskets connection at the edge not to standard', 'NTS'),
    ('6957702f', 'Colour of grout dove grey not consistent', 'NTS'),
    ('3cf49a3d', 'Tile skirting missing grout as indicated', 'NTS'),
    ('7414ad92', 'DB missing screws', 'NTS'),
    ('6b89724d', 'Fluorescent led 2x bulbs need to be cleaned', 'NTS'),
    ('13ec6997', 'Fridge double plug loose', 'NTS'),
    ('470a5289', 'Carcass not painted and chipped', 'NTS'),
    ('470a5289', 'Handles are scratched as indicated', 'NTS'),
    ('445ab368', 'Runners have sand inside', 'NTS'),
    ('25bd6002', 'Top to be cleaned', 'NTS'),
    ('3738af64', 'Left lock is loose', 'NTS'),
    ('5fe88982', 'Leg support loose and to be cleaned', 'NTS'),
    ('9f743e7d', 'Handle scratched as indicated', 'NTS'),
    # LOUNGE
    ('feafbe9d', 'Grout is not grey in some areas as indicated', 'NTS'),
    ('ed852bc0', 'Only one light bulb', 'NTS'),
    ('fa47bce5', 'Residue to be cleaned on double plug on 09 wall', 'NTS'),
    ('d18c9cb7', 'Single light switch to be cleaned', 'NTS'),
    # BATHROOM
    ('f27ee884', 'Hinges to be repainted', 'NTS'),
    ('39fe1eda', 'WC indicator bolt and thumb turn not functioning', 'NTS'),
    ('6975f032', 'Airbrick above door to be cleaned', 'NTS'),
    ('a0481b36', 'Airbrick in shower to be cleaned', 'NTS'),
    ('6f34a0f5', 'WC feels loose', 'NTS'),
    # BEDROOM A
    ('afcc1bc2', 'Chipped paint as indicated', 'NTS'),
    ('212cf40b', 'Chipped frame and scratched as indicated', 'NTS'),
    ('e6f434e1', 'To be cleaned (hand marks)', 'NTS'),
    ('0a294996', 'Glass to be cleaned', 'NTS'),
    ('76ec5f36', 'Residue to be cleaned', 'NTS'),
    ('dc0e02ee', 'Has chipped paint finish', 'NTS'),
    # BEDROOM B
    ('340d94a3', 'Paint work is chipped as indicated', 'NTS'),
    ('622ed9f0', 'Door frame chipped as indicated', 'NTS'),
    ('4605f30f', 'Plaster recess at ceiling to be cleaned', 'NTS'),
    ('81520953', 'Grout missing as indicated', 'NTS'),
    ('a11aff40', 'Wall chipped near panel heater plug on wall 07', 'NTS'),
    ('a7f0db32', 'Hinges missing screw as indicated', 'NTS'),
    # BEDROOM C
    ('80177e8e', 'All round finish checked but door to be cleaned', 'NTS'),
    ('91db75ab', 'Chipped paint as indicated', 'NTS'),
    ('3f2f2146', 'Glass to be cleaned', 'NTS'),
    ('13960def', 'Gaskets to be checked or redone as indicated', 'NTS'),
    # BEDROOM D
    ('66cc0d36', 'Chipped paint as indicated', 'NTS'),
    ('05c84b01', 'Chipped paint at top corner and ceiling', 'NTS'),
    ('956b6837', 'Grout not grey as indicated and has a hole', 'NTS'),
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
