"""
Block 6 Import - Unit 050
Inspector: Lindokuhle Zulu (insp-005)
Date: 2026-02-03
Defects: 76
"""
import sqlite3
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

UNIT_NUMBER = '050'
INSPECTOR_ID = 'insp-005'
INSPECTOR_NAME = 'Lindokuhle Zulu'
INSPECTION_DATE = '2026-02-03'
TENANT = 'MONOGRAPH'
CYCLE_ID = '36e85327'

DEFECTS = [
    # KITCHEN
    ('16e941da', 'Paint not clean and damaged', 'NTS'),
    ('485aba2b', 'Splash back wrap at sink is chipped', 'NTS'),
    ('828b90e9', 'Missing grout between tiles and tile trim at sink', 'NTS'),
    ('828b90e9', 'Grout is damaged at sink splash back', 'NTS'),
    ('5317757a', 'Missing grout between tiles and tile trim at stove splash back top and side', 'NTS'),
    ('637c7b25', 'Stove splash back tile is chipped', 'NTS'),
    ('065b6eb7', 'Window frame needs to be cleaned', 'NTS'),
    ('cbaefabd', 'Glass needs to be cleaned', 'NTS'),
    ('065b6eb7', 'Window frame needs to be cleaned', 'NTS'),
    ('707304a2', 'Glass needs to be cleaned', 'NTS'),
    ('bdafda18', 'Soft joint application is not consistent', 'NTS'),
    ('522b4aeb', 'Chipped tiles as indicated', 'NTS'),
    ('6957702f', 'Grout colour is not consistent', 'NTS'),
    ('3cf49a3d', 'Missing grout between floor and tile skirting', 'NTS'),
    ('255488c3', 'Hinges are rusting as indicated', 'NTS'),
    ('624544cd', 'Bin drawer carcass needs to be cleaned', 'NTS'),
    ('445ab368', 'Bin drawer runners have sand', 'NTS'),
    ('09e5b0d4', 'Counter seating fixing to wall is not to standard', 'NTS'),
    ('5fe88982', 'Counter seating leg support is not stable', 'NTS'),
    ('ddd7b868', 'Lockable pack 1 and 2 carcass needs to be cleaned', 'NTS'),
    ('7f7ddc15', 'Broom cupboard is chipped as indicated', 'NTS'),
    # LOUNGE
    ('c248c406', 'Paint needs to be cleaned', 'NTS'),
    ('3cb1b144', 'Chipped tiles as indicated', 'NTS'),
    ('feafbe9d', 'Grout colour is not consistent', 'NTS'),
    ('a46f716d', 'Grout missing between tile skirting and floor', 'NTS'),
    ('d7863733', 'Ceiling paint is scratched', 'NTS'),
    # BEDROOM A
    ('04796e27', 'Paint is not applied properly at the top of the door', 'NTS'),
    ('2b8649e7', 'Paint is overlapping as indicated', 'NTS'),
    ('eae7e6e1', 'Door scratches against the frame', 'NTS'),
    ('afcc1bc2', 'Frame finish is scratched as indicated', 'NTS'),
    ('e6f434e1', 'Hole in the plaster as indicated', 'NTS'),
    ('0a294996', 'Glass needs to be cleaned', 'NTS'),
    ('41c9bd11', 'Chipped tiles as indicated', 'NTS'),
    ('e1d9e932', 'Damaged grout as indicated', 'NTS'),
    ('14eb7511', 'Missing grout between tile skirting and floor', 'NTS'),
    ('03e99050', 'Study desk missing one screw to wall', 'NTS'),
    ('03e99050', 'Study desk finish has a scratch as indicated', 'NTS'),
    # BEDROOM B
    ('31774738', 'Door does not close, hits against the frame', 'NTS'),
    ('b1f2960d', 'Door finish is scratched', 'NTS'),
    ('b1f2960d', 'Paint finish is chipped as indicated', 'NTS'),
    ('340d94a3', 'Frame finish is scratched as indicated', 'NTS'),
    ('a7d14262', 'Wall paint orchid bay is scratched as indicated', 'NTS'),
    ('f2df64a6', 'Paint is not applied equally as indicated', 'NTS'),
    ('09b9fc9b', 'Window frame needs to be cleaned', 'NTS'),
    ('59a35f5a', 'Glass needs to be cleaned', 'NTS'),
    ('2ed16ab7', 'Tiles are chipped as indicated', 'NTS'),
    ('1136f030', 'Gap under B.I.C. and tile skirting', 'NTS'),
    # BEDROOM C
    ('80177e8e', 'Door finish is chipped as indicated', 'NTS'),
    ('6bc58353', 'Overlapping paint as indicated', 'NTS'),
    ('e833bf33', 'Door scratches against the frame', 'NTS'),
    ('9fdcd89e', 'Frame finish is scratched as indicated', 'NTS'),
    ('9fdcd89e', 'Rubber studs on frame damage the door finish', 'NTS'),
    ('5628303a', 'Overlapping paint as indicated', 'NTS'),
    ('85620ac4', 'Tiles are chipped as indicated', 'NTS'),
    ('6a0771ae', 'Grout missing between tile skirting and floor', 'NTS'),
    ('f42cffed', 'Study desk light has a screw that is not all the way in', 'NTS'),
    # BEDROOM D
    ('45dd2301', 'Overlapping paint as indicated', 'NTS'),
    ('c0183fae', 'Door is scratching against the floor', 'NTS'),
    ('66cc0d36', 'Frame finish is scratched as indicated', 'NTS'),
    ('1fb635e9', 'Glass needs to be cleaned', 'NTS'),
    ('4a354d81', 'Window hinge is rusting', 'NTS'),
    ('54ac6a45', 'Tiles are scratched as indicated', 'NTS'),
    ('a39a8899', 'Missing grout between floor and tile skirting', 'NTS'),
    ('263b99ba', 'B.I.C. carcass needs to be cleaned', 'NTS'),
    ('b38587a1', 'Study desk finish is scratched as indicated', 'NTS'),
    # BATHROOM
    ('f27ee884', 'Door scratches against the frame when being closed', 'NTS'),
    ('e326b993', 'Frame finish is damaged as indicated', 'NTS'),
    ('e326b993', 'Rubber studs on frame damage the door finish', 'NTS'),
    ('c16fbe1e', 'Bathroom lock gets stuck when being closed or opened', 'NTS'),
    ('3016c121', 'Missing grout between floor and tile trim at shower step', 'NTS'),
    ('df84942f', 'Gap between tiles and tile trim at duct wall corner', 'NTS'),
    ('347c7f63', 'Gap between tiles and tile trim at window reveal', 'NTS'),
    ('f1438790', 'Holes in grout', 'NTS'),
    ('107b77d6', 'Ceiling mounted light has one bulb', 'NTS'),
    ('1beaecc9', 'Water is not coming out of the rose', 'NTS'),
    ('b3cb1299', 'Arm is loose and not finished', 'NTS'),
]

def gen_id():
    return uuid.uuid4().hex[:8]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def fuzzy_match(text, candidates, threshold=0.7):
    best_match = None
    best_score = 0
    text_lower = text.lower().strip()
    for candidate in candidates:
        score = SequenceMatcher(None, text_lower, candidate.lower().strip()).ratio()
        if score > best_score:
            best_score = score
            best_match = candidate
    if best_score >= threshold:
        return best_match, best_score
    return None, 0

def wash_description(cur, item_template_id, raw_desc):
    cur.execute("""
        SELECT ct.category_name
        FROM item_template it
        JOIN category_template ct ON it.category_id = ct.id
        WHERE it.id = ?
    """, (item_template_id,))
    cat_row = cur.fetchone()
    cat_name = cat_row[0] if cat_row else 'UNKNOWN'
    cur.execute("""
        SELECT description FROM defect_library
        WHERE tenant_id = ? AND item_template_id = ?
        ORDER BY usage_count DESC
    """, (TENANT, item_template_id))
    item_entries = [r[0] for r in cur.fetchall()]
    if item_entries:
        match, score = fuzzy_match(raw_desc, item_entries)
        if match:
            return match, f"item-specific (score={score:.2f})", cat_name
    cur.execute("""
        SELECT description FROM defect_library
        WHERE tenant_id = ? AND category_name = ? AND item_template_id IS NULL
        ORDER BY usage_count DESC
    """, (TENANT, cat_name))
    cat_entries = [r[0] for r in cur.fetchall()]
    if cat_entries:
        match, score = fuzzy_match(raw_desc, cat_entries)
        if match:
            return match, f"category-fallback (score={score:.2f})", cat_name
    cleaned = raw_desc.strip()
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned, "NEW (added to library)", cat_name

def main():
    conn = sqlite3.connect('/var/data/inspections.db')
    cur = conn.cursor()
    now = now_iso()
    print(f"=== IMPORT: Unit {UNIT_NUMBER} ===")
    print(f"Inspector: {INSPECTOR_NAME} ({INSPECTOR_ID})")
    print(f"Date: {INSPECTION_DATE}")
    print(f"Cycle: {CYCLE_ID}")
    print()
    print("--- VERIFYING TEMPLATE IDs ---")
    all_valid = True
    for template_id, raw_desc, dtype in DEFECTS:
        cur.execute('SELECT id FROM item_template WHERE id=? AND tenant_id=?', (template_id, TENANT))
        if not cur.fetchone():
            print(f"  MISSING: {template_id} ({raw_desc})")
            all_valid = False
    if not all_valid:
        print("ABORTING - fix template IDs")
        conn.close()
        return
    print(f"  All {len(DEFECTS)} template IDs verified")
    print()
    cur.execute('SELECT id FROM unit WHERE unit_number=? AND tenant_id=?', (UNIT_NUMBER, TENANT))
    row = cur.fetchone()
    if not row:
        print(f"ERROR: Unit {UNIT_NUMBER} not found")
        conn.close()
        return
    unit_id = row[0]
    print(f"Unit ID: {unit_id}")
    cur.execute('SELECT id, status FROM inspection WHERE unit_id=? AND cycle_id=?', (unit_id, CYCLE_ID))
    row = cur.fetchone()
    if row:
        insp_id, insp_status = row
        print(f"Existing inspection: {insp_id} (status={insp_status})")
        if insp_status not in ('not_started', 'in_progress'):
            print(f"WARNING: Inspection already at {insp_status} - skipping")
            conn.close()
            return
    else:
        insp_id = gen_id()
        cur.execute("""
            INSERT INTO inspection
            (id, tenant_id, unit_id, cycle_id, inspection_date,
             inspector_id, inspector_name, status, started_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'in_progress', ?, ?, ?)
        """, (insp_id, TENANT, unit_id, CYCLE_ID, INSPECTION_DATE, INSPECTOR_ID, INSPECTOR_NAME, now, now, now))
        print(f"Created inspection: {insp_id}")
    cur.execute("UPDATE inspection SET inspector_id=?, inspector_name=?, updated_at=? WHERE id=?",
                (INSPECTOR_ID, INSPECTOR_NAME, now, insp_id))
    cur.execute("UPDATE cycle_unit_assignment SET inspector_id=? WHERE cycle_id=? AND unit_id=?",
                (INSPECTOR_ID, CYCLE_ID, unit_id))
    print(f"Inspector set: {INSPECTOR_NAME}")
    cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=?', (insp_id,))
    existing_items = cur.fetchone()[0]
    if existing_items > 0:
        print(f"Inspection items already exist: {existing_items}")
    else:
        cur.execute('SELECT id FROM item_template WHERE tenant_id=?', (TENANT,))
        templates = cur.fetchall()
        for t in templates:
            cur.execute("""
                INSERT INTO inspection_item
                (id, tenant_id, inspection_id, item_template_id, status, marked_at)
                VALUES (?, ?, ?, ?, 'pending', NULL)
            """, (gen_id(), TENANT, insp_id, t[0]))
        print(f"Created {len(templates)} inspection items")
    cur.execute("""
        SELECT DISTINCT ii.item_template_id
        FROM inspection_item ii
        JOIN inspection i ON ii.inspection_id = i.id
        WHERE i.cycle_id = '792812c7' AND ii.status = 'skipped'
    """)
    excluded_ids = set(r[0] for r in cur.fetchall())
    print(f"Exclusion template IDs from Block 5: {len(excluded_ids)}")
    skipped_count = 0
    for eid in excluded_ids:
        cur.execute("UPDATE inspection_item SET status='skipped', marked_at=? WHERE inspection_id=? AND item_template_id=?",
                    (now, insp_id, eid))
        skipped_count += cur.rowcount
    print(f"Marked skipped: {skipped_count}")
    print()
    print("--- EXCLUSION OVERLAP CHECK ---")
    dropped = []
    clean_defects = []
    for template_id, raw_desc, dtype in DEFECTS:
        if template_id in excluded_ids:
            dropped.append((template_id, raw_desc))
            print(f"  DROPPED (excluded): [{template_id}] {raw_desc}")
        else:
            clean_defects.append((template_id, raw_desc, dtype))
    if dropped:
        print(f"Dropped {len(dropped)} defects on excluded items")
    else:
        print("No overlaps")
    print()
    print("--- DEFECT WASH + CREATE ---")
    new_library = []
    defect_count = 0
    for template_id, raw_desc, dtype in clean_defects:
        washed_desc, wash_source, cat_name = wash_description(cur, template_id, raw_desc)
        if "NEW" in wash_source:
            new_library.append((template_id, cat_name, washed_desc))
        print(f"  [{template_id}] Raw: {raw_desc}")
        print(f"            Washed: {washed_desc} [{wash_source}]")
        defect_id = gen_id()
        defect_type = 'not_installed' if dtype == 'NI' else 'not_to_standard'
        cur.execute("""
            INSERT INTO defect
            (id, tenant_id, unit_id, item_template_id, raised_cycle_id,
             defect_type, status, original_comment, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, ?)
        """, (defect_id, TENANT, unit_id, template_id, CYCLE_ID, defect_type, washed_desc, now, now))
        item_status = 'not_installed' if dtype == 'NI' else 'not_to_standard'
        cur.execute("UPDATE inspection_item SET status=?, comment=?, marked_at=? WHERE inspection_id=? AND item_template_id=?",
                    (item_status, washed_desc, now, insp_id, template_id))
        defect_count += 1
    print(f"\nDefects created: {defect_count}")
    cur.execute("UPDATE inspection_item SET status='ok', marked_at=? WHERE inspection_id=? AND status='pending'", (now, insp_id))
    ok_count = cur.rowcount
    print(f"Marked OK: {ok_count}")
    if new_library:
        print()
        print("--- NEW LIBRARY ENTRIES ---")
        for template_id, cat_name, desc in new_library:
            lib_id = gen_id()
            cur.execute("""
                INSERT INTO defect_library
                (id, tenant_id, category_name, item_template_id, description,
                 usage_count, is_system, created_at)
                VALUES (?, ?, ?, ?, ?, 1, 0, ?)
            """, (lib_id, TENANT, cat_name, template_id, desc, now))
            print(f"  Added: [{cat_name}] {desc}")
        print(f"New library entries: {len(new_library)}")
    cur.execute("UPDATE inspection SET status='submitted', submitted_at=?, updated_at=? WHERE id=?", (now, now, insp_id))
    cur.execute("UPDATE unit SET status='in_progress' WHERE id=? AND status='not_started'", (unit_id,))
    print()
    print("=== VERIFICATION ===")
    cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=? AND status=?', (insp_id, 'skipped'))
    print(f"Skipped: {cur.fetchone()[0]} (expected 85)")
    cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=? AND status=?', (insp_id, 'ok'))
    print(f"OK: {cur.fetchone()[0]}")
    cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=? AND status IN (?,?)', (insp_id, 'not_to_standard', 'not_installed'))
    print(f"NTS/NI: {cur.fetchone()[0]}")
    cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=? AND status=?', (insp_id, 'pending'))
    print(f"Pending: {cur.fetchone()[0]} (expected 0)")
    cur.execute('SELECT COUNT(*) FROM defect WHERE unit_id=? AND raised_cycle_id=? AND status=?', (unit_id, CYCLE_ID, 'open'))
    print(f"Defects: {cur.fetchone()[0]}")
    total = 0
    for status in ['skipped', 'ok', 'not_to_standard', 'not_installed', 'pending']:
        cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=? AND status=?', (insp_id, status))
        total += cur.fetchone()[0]
    print(f"Total items: {total} (expected 523)")
    conn.commit()
    print()
    print("COMMITTED SUCCESSFULLY")
    conn.close()

if __name__ == '__main__':
    main()
