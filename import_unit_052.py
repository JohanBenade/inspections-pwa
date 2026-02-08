"""
Block 6 Import - Unit 052
Inspector: Lindokuhle Zulu (insp-005)
Date: 2026-02-04
Defects: 80
"""
import sqlite3
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

UNIT_NUMBER = '052'
INSPECTOR_ID = 'insp-005'
INSPECTOR_NAME = 'Lindokuhle Zulu'
INSPECTION_DATE = '2026-02-04'
TENANT = 'MONOGRAPH'
CYCLE_ID = '36e85327'

DEFECTS = [
    # KITCHEN
    ('99a8d423', 'Plastered recess above door chipped finish', 'NTS'),
    ('16e941da', 'Paint is chipped and dirty as indicated', 'NTS'),
    ('828b90e9', 'Grout missing in between tiles at sink splash back', 'NTS'),
    ('5317757a', 'Grout missing in between tiles and tile trim at stove splash back', 'NTS'),
    ('065b6eb7', 'Window coating is damaged as indicated', 'NTS'),
    ('cbaefabd', 'Glass needs to be cleaned', 'NTS'),
    ('065b6eb7', 'Window frame needs to be cleaned', 'NTS'),
    ('065b6eb7', 'Tape needs to be removed in frame', 'NTS'),
    ('707304a2', 'Glass is broken as indicated', 'NTS'),
    ('bdafda18', 'Soft joint looks damaged as indicated', 'NTS'),
    ('522b4aeb', 'Tiles are chipped as indicated', 'NTS'),
    ('3cf49a3d', 'Grout missing in between tile skirting and floor', 'NTS'),
    ('3cf49a3d', 'Gap between tile skirting and joineries as indicated', 'NTS'),
    ('5158daf4', 'Sink pack carcass needs to be cleaned and is chipped', 'NTS'),
    ('255488c3', 'Rusted hinges on sink pack', 'NTS'),
    ('2d37363a', 'Sink pack top is chipped as indicated', 'NTS'),
    ('28814cf6', 'Lower drawer handle is chipped as indicated', 'NTS'),
    ('5fe88982', 'Counter seating leg support is not stable', 'NTS'),
    ('09e5b0d4', 'Counter seating top is scratched as indicated', 'NTS'),
    ('7f7ddc15', 'Broom cupboard carcass needs to be cleaned', 'NTS'),
    ('7f7ddc15', 'Broom cupboard finish inside is scratched as indicated', 'NTS'),
    ('38b69f7c', 'Eye level pack carcass damaged as indicated', 'NTS'),
    # LOUNGE
    ('c248c406', 'Paint has marks as indicated', 'NTS'),
    ('3cb1b144', 'Chipped tiles as indicated', 'NTS'),
    ('a46f716d', 'Missing grout in between tile skirting and floor', 'NTS'),
    ('d7863733', 'Ceiling paint is scratched', 'NTS'),
    ('d7863733', 'Ceiling has a screw', 'NTS'),
    ('ed852bc0', 'Ceiling mounted light has one bulb', 'NTS'),
    # BEDROOM A
    ('04796e27', 'Door paint needs to be cleaned', 'NTS'),
    ('afcc1bc2', 'Frame is chipped as indicated', 'NTS'),
    ('afcc1bc2', 'Frame paint is chipped as indicated', 'NTS'),
    ('557dfea3', 'Lockset cylinder and thumb turn stuck', 'NTS'),
    ('e6f434e1', 'Wall has marks as indicated', 'NTS'),
    ('59a4040c', 'Divina paint is chipped as indicated', 'NTS'),
    ('db6da547', 'Tapes need to be removed in window frame', 'NTS'),
    ('0a294996', 'Glass needs to be cleaned', 'NTS'),
    ('e1d9e932', 'Grout has holes in it', 'NTS'),
    ('14eb7511', 'Grout missing in between tile and tile skirting', 'NTS'),
    ('14eb7511', 'Gap between B.I.C. and tile skirting', 'NTS'),
    ('557d6486', 'B.I.C. carcass needs to be cleaned', 'NTS'),
    ('03e99050', 'Study desk loose screws to wall as indicated', 'NTS'),
    # BEDROOM B
    ('b1f2960d', 'Door is splitting at the top', 'NTS'),
    ('b1f2960d', 'Overlapping paint on door', 'NTS'),
    ('340d94a3', 'Frame finish is chipped as indicated', 'NTS'),
    ('8b80d8a5', 'Frame paint is scratched as indicated', 'NTS'),
    ('aef89fec', 'Door hits against steel part of door stop not the rubber', 'NTS'),
    ('a7d14262', 'Paint is chipped above the door', 'NTS'),
    ('f2df64a6', 'Wall has paint marks as indicated', 'NTS'),
    ('4605f30f', 'Plaster recess is chipped above the door', 'NTS'),
    ('59a35f5a', 'Glass needs to be cleaned', 'NTS'),
    ('2ed16ab7', 'Tile is chipped as indicated', 'NTS'),
    ('81520953', 'Grout has gaps', 'NTS'),
    ('1136f030', 'Gap between tile skirting and floor and B.I.C.', 'NTS'),
    # BEDROOM C
    ('80177e8e', 'Door needs to be cleaned', 'NTS'),
    ('6bc58353', 'Overlapping paint on door', 'NTS'),
    ('9fdcd89e', 'Frame finish is damaged as indicated', 'NTS'),
    ('c2e3219c', 'Residence lock needs to be cleaned', 'NTS'),
    ('5628303a', 'Paint is scratched as indicated', 'NTS'),
    ('53a6348d', 'Paint needs to be cleaned as indicated', 'NTS'),
    ('1fae2eac', 'Window frame needs to be cleaned', 'NTS'),
    ('3f2f2146', 'Glass needs to be cleaned', 'NTS'),
    ('85620ac4', 'Chipped tiles as indicated', 'NTS'),
    ('f34b4fe9', 'Grout missing in between tiles as indicated', 'NTS'),
    # BEDROOM D
    ('212d83e1', 'Door is damaged as indicated', 'NTS'),
    ('66cc0d36', 'Frame finish is chipped as indicated', 'NTS'),
    ('248d3871', 'Paint orchid bay is scratched as indicated', 'NTS'),
    ('0a0fb9b6', 'Plaster recess at ceiling is not consistent', 'NTS'),
    ('1fb635e9', 'Glass needs to be cleaned', 'NTS'),
    ('a39a8899', 'Missing grout in between tile skirting and floor', 'NTS'),
    ('b38587a1', 'Study desk does not look levelled', 'NTS'),
    # BATHROOM
    ('b6b5d166', 'Door has chipped edge as indicated', 'NTS'),
    ('e326b993', 'Frame finish is chipped as indicated', 'NTS'),
    ('ef937d8f', 'Full height tiling all round is not completed', 'NTS'),
    ('df84942f', 'Missing grout in between tile trim and tiles in duct wall corner', 'NTS'),
    ('ef937d8f', 'Chipped tiles as indicated', 'NTS'),
    ('fc632a8a', 'Shadow line recess at ceiling is not complete', 'NTS'),
    ('07d644a5', 'Window coating is chipped', 'NTS'),
    ('852c37b8', 'Mosaic tiles in shower need to be cleaned', 'NTS'),
    ('107b77d6', 'Ceiling mounted light has one bulb', 'NTS'),
    ('8667f32c', 'WC not flushed to wall', 'NTS'),
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
