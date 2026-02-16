import sqlite3, uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

UNIT_NUMBER = '134'
INSPECTOR_ID = 'insp-005'
INSPECTOR_NAME = 'Lindokuhle Zulu'
INSPECTION_DATE = '2026-02-13'
TENANT = 'MONOGRAPH'
CYCLE_ID = '179b2b9d'
EXCLUSION_SOURCE_CYCLE = '792812c7'

DEFECTS = [
    # KITCHEN (Frame + Striker = front door, DROPPED)
    ('16e941da', 'Brown spots in the paint as indicated', 'NTS'),
    ('7889a386', 'Gap between tile trim and tile at window 1a as indicated', 'NTS'),
    ('485aba2b', 'Gap at tile trim at sink splash back as indicated', 'NTS'),
    ('943ade71', 'Gap in grout as indicated', 'NTS'),
    ('76477531', 'Chipped tile as indicated', 'NTS'),
    ('cbaefabd', 'Glass needs to be cleaned', 'NTS'),
    ('707304a2', 'Glass needs to be cleaned', 'NTS'),
    ('522b4aeb', 'Chipped tile as indicated', 'NTS'),
    ('6957702f', 'Grout needs to be cleaned', 'NTS'),
    ('3cf49a3d', 'Gap between tile skirting and joineries', 'NTS'),
    ('369caaf1', 'Chipped part as indicated', 'NTS'),
    ('470a5289', 'Carcass needs to be cleaned as indicated', 'NTS'),
    ('255488c3', 'Hinges have rust', 'NTS'),
    ('0c881d18', 'Top has a rough part as indicated', 'NTS'),
    ('684bf2ed', 'Carcass needs to be cleaned as indicated', 'NTS'),
    ('25bd6002', 'Top has a rough part as indicated', 'NTS'),
    ('c64ad084', 'Fixing to wall is not to standard', 'NTS'),
    ('7af717d1', 'Top has a rough part as indicated', 'NTS'),
    ('406b0286', 'Finish is peeling as indicated', 'NTS'),
    # LOUNGE
    ('c248c406', 'Paint orchid bay has dirty marks as indicated', 'NTS'),
    ('3cb1b144', 'Chipped tile as indicated', 'NTS'),
    ('a46f716d', 'Gap in tile skirting as indicated', 'NTS'),
    ('a4163cb8', 'Cracks in plaster recess', 'NTS'),
    # BEDROOM A (Panel heater = FF&E excluded, overlap will drop)
    ('afcc1bc2', 'Finish needs to be cleaned', 'NTS'),
    ('212cf40b', 'Finish is chipped as indicated', 'NTS'),
    ('2b8649e7', 'Paint on outside is chipped as indicated', 'NTS'),
    ('e6f434e1', 'Paint orchid bay is chipped as indicated and needs to be cleaned', 'NTS'),
    ('14eb7511', 'Gap between tile skirting and B.I.C', 'NTS'),
    ('a1b8e817', 'Finish has paint marks as indicated', 'NTS'),
    ('ed43d43a', 'Screw is missing', 'NTS'),
    ('5d45a701', 'Needs to be cleaned', 'NTS'),
    # BEDROOM B
    ('622ed9f0', 'Finish is scratched as indicated', 'NTS'),
    ('59a35f5a', 'Glass needs to be cleaned', 'NTS'),
    ('6348ca23', 'Hinges have rust as indicated', 'NTS'),
    ('1136f030', 'Gap between tile skirting and B.I.C', 'NTS'),
    ('3b44bd96', 'Screw is missing', 'NTS'),
    # BEDROOM C
    ('34010417', 'Door is chipped as indicated', 'NTS'),
    ('9fdcd89e', 'Finish is scratched as indicated', 'NTS'),
    ('91db75ab', 'Finish is chipped as indicated', 'NTS'),
    ('e553bad3', 'Lockset cylinder and thumb turn is not working', 'NTS'),
    ('6a0771ae', 'Gap between tile skirting and the floor', 'NTS'),
    ('8911e60e', 'Gap between tile skirting and B.I.C', 'NTS'),
    ('d41739e5', 'Screw is missing', 'NTS'),
    # BEDROOM D
    ('2563eaaf', 'Door is chipped as indicated', 'NTS'),
    ('9d6fe4a5', 'Screws are missing in residence lock handle', 'NTS'),
    ('54ac6a45', 'Chipped tiles as indicated', 'NTS'),
    ('a39a8899', 'Gap between tile skirting and B.I.C', 'NTS'),
    ('b41bf52d', 'Paint orchid bay is rough', 'NTS'),
    ('b1b7e7ec', 'Screw is not properly put in the study desk light', 'NTS'),
    ('97dbb539', 'Finish is chipped as indicated', 'NTS'),
    # BATHROOM
    ('a9c136be', 'Finish is scratched as indicated', 'NTS'),
    ('6f84fade', 'Finish has overlapping paint as indicated', 'NTS'),
    ('39fe1eda', 'WC indicator bolt and thumb turn is not working', 'NTS'),
    ('3016c121', 'Gap between tile trim and tile on shower step as indicated', 'NTS'),
    ('df84942f', 'Gap between tile trim and tile on duct wall corner as indicated', 'NTS'),
    ('ef937d8f', 'Chipped tile as indicated', 'NTS'),
    ('347c7f63', 'Gap between tile trim and tile in shower as indicated', 'NTS'),
    ('8fa8781c', 'Grout needs to be cleaned', 'NTS'),
    ('e6260484', 'Tile is covered by grout as indicated', 'NTS'),
    ('88b333f7', 'Portion of fall to trap is covered by grout', 'NTS'),
    ('b9805e6c', 'Shut off valve plate is loose', 'NTS'),
    ('78f827b4', 'Plate in the mixer is loose', 'NTS'),
    ('c1b4d353', 'Plate in the arm is loose', 'NTS'),
    ('3fbc1db8', 'Shut off valve hot plate is loose', 'NTS'),
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
