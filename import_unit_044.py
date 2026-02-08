"""
Block 6 Import Script - Unit 044
65 defects (64 NTS + 1 NI), 5 dropped (3 front door + 1 soft joint + 1 panel heater FF&E)
"""
import sqlite3
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

UNIT_NUMBER = '044'
INSPECTOR_ID = 'insp-005'
INSPECTOR_NAME = 'Lindokuhle Zulu'
INSPECTION_DATE = '2026-02-02'
TENANT = 'MONOGRAPH'
CYCLE_ID = '36e85327'

DEFECTS = [
    ('485aba2b', 'Missing grout in between tiles and tile trim as indicated', 'NTS'),
    ('637c7b25', 'Missing grout in between tile and tile trim', 'NTS'),
    ('cbaefabd', 'Glass needs to be cleaned', 'NTS'),
    ('707304a2', 'Glass needs to be cleaned', 'NTS'),
    ('fa56c99f', 'Inconsistent tile set out', 'NTS'),
    ('3cf49a3d', 'Grout missing in between tile skirting and floor', 'NTS'),
    ('7414ad92', 'DB is not installed', 'NI'),
    ('5158daf4', 'Carcass back wall needs to be painted', 'NTS'),
    ('255488c3', 'Hinges look water damaged', 'NTS'),
    ('5158daf4', 'There is a gap between sink pack and the wall', 'NTS'),
    ('445ab368', 'There is sand in the runners', 'NTS'),
    ('09e5b0d4', 'Fixing to wall not done well / not to standard', 'NTS'),
    ('5fe88982', 'Leg support is loose', 'NTS'),
    ('e96314c5', 'There are oil marks on the finish', 'NTS'),
    ('a46f716d', 'Grout is missing in between flooring and skirting', 'NTS'),
    ('d7863733', 'Paint-orchid bay is chipped', 'NTS'),
    ('a4163cb8', 'Plaster recess is damaged', 'NTS'),
    ('ed852bc0', 'There is only one bulb', 'NTS'),
    ('557dfea3', 'Handle does not swing properly', 'NTS'),
    ('e6f434e1', 'Chipped plaster', 'NTS'),
    ('59a4040c', 'The paint is chipped as indicated', 'NTS'),
    ('0a294996', 'Window needs to be cleaned', 'NTS'),
    ('41c9bd11', 'Chipped tile', 'NTS'),
    ('14eb7511', 'Grout missing in between tile skirting and floor as indicated', 'NTS'),
    ('14eb7511', 'Gap between tile skirting and under B.I.C', 'NTS'),
    ('b1f2960d', 'Rubs against the frame when closing', 'NTS'),
    ('340d94a3', 'Finish is damaged', 'NTS'),
    ('8b80d8a5', 'Paint on outside is damaged', 'NTS'),
    ('f2df64a6', 'Damaged paint as indicated', 'NTS'),
    ('4605f30f', 'Gaps in plaster recess at ceiling', 'NTS'),
    ('59a35f5a', 'Window needs to be cleaned', 'NTS'),
    ('81520953', 'Holes in grout as indicated', 'NTS'),
    ('1136f030', 'No grout in between tile skirtings', 'NTS'),
    ('1136f030', 'Gaps between tile skirting and the floor', 'NTS'),
    ('5d1dc2bd', 'The screw is loose', 'NTS'),
    ('80177e8e', 'Finish is damaged', 'NTS'),
    ('9fdcd89e', 'Frame finish is damaged as indicated', 'NTS'),
    ('3f2f2146', 'Window needs to be cleaned', 'NTS'),
    ('85620ac4', 'Chipped as indicated', 'NTS'),
    ('6a0771ae', 'Missing grout in between floor and tile skirting', 'NTS'),
    ('6a0771ae', 'Gaps between tile skirting and B.I.C', 'NTS'),
    ('f42cffed', 'One screw is missing', 'NTS'),
    ('6624b692', 'Plaster against the wall is cracking', 'NTS'),
    ('c0183fae', 'Door is scratching against the frame', 'NTS'),
    ('212d83e1', 'Finish is chipped at the top', 'NTS'),
    ('66cc0d36', 'Damaged paint as indicated', 'NTS'),
    ('3b18b7d5', 'Paints are overlapping', 'NTS'),
    ('c0183fae', 'Hinges are making noise when door is being opened', 'NTS'),
    ('05c84b01', 'Plaster on the wall is damaged as indicated', 'NTS'),
    ('248d3871', 'Paint-orchid bay is scratched', 'NTS'),
    ('bd6a61c0', 'There is inconsistency in paint application', 'NTS'),
    ('1fb635e9', 'Window needs to be cleaned', 'NTS'),
    ('54ac6a45', 'Tile is chipped as indicated', 'NTS'),
    ('a39a8899', 'Grout missing in between tile skirting and the floor', 'NTS'),
    ('a39a8899', 'Gaps between B.I.C and tile skirting', 'NTS'),
    ('263b99ba', 'Backwall has the inconsistent colour', 'NTS'),
    ('135828f3', 'Floating shelf finish has a crack as indicated', 'NTS'),
    ('b38587a1', 'Study desk has a crack against the wall', 'NTS'),
    ('e326b993', 'Frame damaged as indicated', 'NTS'),
    ('c16fbe1e', 'Screw is loose', 'NTS'),
    ('3016c121', 'Tiles are not properly aligned with tile trim on the shower step', 'NTS'),
    ('df84942f', 'Grout missing in between tiles and tile trim on duct wall corner', 'NTS'),
    ('347c7f63', 'There are gaps on window reveal as indicated', 'NTS'),
    ('fc632a8a', 'Shadow line recess at ceiling is not consistent', 'NTS'),
    ('07d644a5', 'Gaps in the frame as indicated', 'NTS'),
    ('0514ada9', 'Glass needs to be cleaned', 'NTS'),
    ('d5c6a122', 'Grout in the shower is not dark grey', 'NTS'),
    ('107b77d6', 'There is only one light bulb', 'NTS'),
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
        cur.execute('SELECT id FROM item_template WHERE id=? AND tenant_id=?',
                    (template_id, TENANT))
        if not cur.fetchone():
            print(f"  MISSING: {template_id} ({raw_desc})")
            all_valid = False
    if not all_valid:
        print("ABORTING - fix template IDs")
        conn.close()
        return
    print(f"  All {len(DEFECTS)} template IDs verified")
    print()
    cur.execute('SELECT id FROM unit WHERE unit_number=? AND tenant_id=?',
                (UNIT_NUMBER, TENANT))
    row = cur.fetchone()
    if not row:
        print(f"ERROR: Unit {UNIT_NUMBER} not found")
        conn.close()
        return
    unit_id = row[0]
    print(f"Unit ID: {unit_id}")
    cur.execute('SELECT id, status FROM inspection WHERE unit_id=? AND cycle_id=?',
                (unit_id, CYCLE_ID))
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
        """, (insp_id, TENANT, unit_id, CYCLE_ID, INSPECTION_DATE,
              INSPECTOR_ID, INSPECTOR_NAME, now, now, now))
        print(f"Created inspection: {insp_id}")
    cur.execute("""
        UPDATE inspection SET inspector_id=?, inspector_name=?, updated_at=?
        WHERE id=?
    """, (INSPECTOR_ID, INSPECTOR_NAME, now, insp_id))
    cur.execute("""
        UPDATE cycle_unit_assignment SET inspector_id=?
        WHERE cycle_id=? AND unit_id=?
    """, (INSPECTOR_ID, CYCLE_ID, unit_id))
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
        cur.execute("""
            UPDATE inspection_item SET status='skipped', marked_at=?
            WHERE inspection_id=? AND item_template_id=?
        """, (now, insp_id, eid))
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
        """, (defect_id, TENANT, unit_id, template_id, CYCLE_ID,
              defect_type, washed_desc, now, now))
        item_status = 'not_installed' if dtype == 'NI' else 'not_to_standard'
        cur.execute("""
            UPDATE inspection_item SET status=?, comment=?, marked_at=?
            WHERE inspection_id=? AND item_template_id=?
        """, (item_status, washed_desc, now, insp_id, template_id))
        defect_count += 1
    print(f"\nDefects created: {defect_count}")
    cur.execute("""
        UPDATE inspection_item SET status='ok', marked_at=?
        WHERE inspection_id=? AND status='pending'
    """, (now, insp_id))
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
    cur.execute("""
        UPDATE inspection SET status='submitted', submitted_at=?, updated_at=?
        WHERE id=?
    """, (now, now, insp_id))
    cur.execute("""
        UPDATE unit SET status='in_progress' WHERE id=? AND status='not_started'
    """, (unit_id,))
    print()
    print("=== VERIFICATION ===")
    cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=? AND status=?',
                (insp_id, 'skipped'))
    print(f"Skipped: {cur.fetchone()[0]} (expected 85)")
    cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=? AND status=?',
                (insp_id, 'ok'))
    print(f"OK: {cur.fetchone()[0]}")
    cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=? AND status IN (?,?)',
                (insp_id, 'not_to_standard', 'not_installed'))
    print(f"NTS/NI: {cur.fetchone()[0]}")
    cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=? AND status=?',
                (insp_id, 'pending'))
    print(f"Pending: {cur.fetchone()[0]} (expected 0)")
    cur.execute('SELECT COUNT(*) FROM defect WHERE unit_id=? AND raised_cycle_id=? AND status=?',
                (unit_id, CYCLE_ID, 'open'))
    print(f"Defects: {cur.fetchone()[0]}")
    total = 0
    for status in ['skipped', 'ok', 'not_to_standard', 'not_installed', 'pending']:
        cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=? AND status=?',
                    (insp_id, status))
        total += cur.fetchone()[0]
    print(f"Total items: {total} (expected 523)")
    conn.commit()
    print()
    print("COMMITTED SUCCESSFULLY")
    conn.close()

if __name__ == '__main__':
    main()
