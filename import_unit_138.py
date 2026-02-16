"""Import Unit 138 - Block 5 1st Floor
Inspector: Lindokuhle Zulu (insp-005) | Date: 13.02.2026
Defects: 63 (all NTS)
Dropped: 1 kitchen front door frame + general notes
"""
import sqlite3, uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

UNIT_NUMBER = '138'
INSPECTOR_ID = 'insp-005'
INSPECTOR_NAME = 'Lindokuhle Zulu'
INSPECTION_DATE = '2026-02-13'
TENANT = 'MONOGRAPH'
CYCLE_ID = '179b2b9d'
EXCLUSION_SOURCE_CYCLE = '792812c7'

DEFECTS = [
    # KITCHEN (14)
    ('485aba2b', 'Gap between tile and tile trim at window 1a as indicated', 'NTS'),
    ('522b4aeb', 'Chipped tiles as indicated', 'NTS'),
    ('3cf49a3d', 'Gaps between tile skirting and joineries', 'NTS'),
    ('5158daf4', 'Carcass is chipped as indicated', 'NTS'),
    ('2d37363a', 'Paint mark on the finish', 'NTS'),
    ('1b23f570', 'Remove plastics from handles', 'NTS'),
    ('28814cf6', 'Remove plastic from handles', 'NTS'),
    ('215c2a34', 'Remove plastics from handles', 'NTS'),
    ('09e5b0d4', 'Fixing to wall is not to standard', 'NTS'),
    ('9d4b7503', 'Top is rough as indicated', 'NTS'),
    ('a2d027f4', 'Remove plastics from handles', 'NTS'),
    ('df9f5a7a', 'Remove plastic from handle', 'NTS'),
    ('8c4b0438', 'Broom cupboard door is not flushed', 'NTS'),
    ('8c97a66a', 'Remove plastics from handles', 'NTS'),
    # BEDROOM A (12)
    ('04796e27', 'Paint is scratched as indicated', 'NTS'),
    ('afcc1bc2', 'Finish is scratched as indicated', 'NTS'),
    ('2b8649e7', 'Paint on outside is chipped as indicated', 'NTS'),
    ('e6f434e1', 'Plaster is not consistent as indicated', 'NTS'),
    ('a1eecb62', 'Paint orchid bay is scratched as indicated', 'NTS'),
    ('59a4040c', 'Overlapping paint', 'NTS'),
    ('41c9bd11', 'Chipped tiles as indicated', 'NTS'),
    ('e1d9e932', 'Gap in grout as indicated', 'NTS'),
    ('14eb7511', 'Gap between tile skirting and floor', 'NTS'),
    ('14eb7511', 'Gap between tile skirting and B.I.C', 'NTS'),
    ('468ece9d', 'Paint marks on the finish', 'NTS'),
    ('03e99050', 'Loose screw', 'NTS'),
    # BEDROOM B (10)
    ('b1f2960d', 'Door is chipped as indicated', 'NTS'),
    ('b1f2960d', 'Overlapping paint at the top of the door', 'NTS'),
    ('340d94a3', 'Finish has a scratch as indicated', 'NTS'),
    ('8b80d8a5', 'Paint on outside has paint marks', 'NTS'),
    ('f2df64a6', 'Has dirt and scratches as indicated', 'NTS'),
    ('09b9fc9b', 'Frame has paint marks', 'NTS'),
    ('6348ca23', 'Hinge has a rust as indicated', 'NTS'),
    ('2ed16ab7', 'Chipped tile as indicated', 'NTS'),
    ('1136f030', 'Gap between tile skirting and B.I.C', 'NTS'),
    ('15dc31bd', 'Handles are not aligned', 'NTS'),
    # BEDROOM C (7)
    ('6bc58353', 'Paint on outside is not consistent as indicated', 'NTS'),
    ('9fdcd89e', 'Finish has a scratch as indicated', 'NTS'),
    ('24dfa887', 'Paint on outside is scratched as indicated', 'NTS'),
    ('5628303a', 'Paint orchid bay has paint marks', 'NTS'),
    ('1fae2eac', 'Frame has paint marks', 'NTS'),
    ('6a0771ae', 'Gap between tile skirting and B.I.C', 'NTS'),
    ('f3578740', 'Handles are not aligned', 'NTS'),
    # BEDROOM D (11)
    ('212d83e1', 'Paint is not applied at the top of the door', 'NTS'),
    ('212d83e1', 'Crack at the door', 'NTS'),
    ('66cc0d36', 'Finish is chipped as indicated', 'NTS'),
    ('05c84b01', 'Plaster is chipped under the study desk', 'NTS'),
    ('248d3871', 'Paint orchid bay is chipped under the study desk', 'NTS'),
    ('0a0fb9b6', 'Plaster recess at ceiling has a crack', 'NTS'),
    ('54ac6a45', 'Crack on the tile as indicated', 'NTS'),
    ('a39a8899', 'Gap between tile skirting and B.I.C', 'NTS'),
    ('b1b7e7ec', 'Screw at the study desk light is not all the way in', 'NTS'),
    ('07ad730b', 'Paint mark on finish', 'NTS'),
    ('cd7d1627', 'Handles are not aligned', 'NTS'),
    # BATHROOM (9)
    ('b6b5d166', 'Lines at the door', 'NTS'),
    ('e326b993', 'Finish is scratched', 'NTS'),
    ('c16fbe1e', 'WC indicator bolt and thumb turn is not working', 'NTS'),
    ('df84942f', 'Gap between tile trim and tile on duct wall corner', 'NTS'),
    ('347c7f63', 'Gap between tile trim and tile on window reveal', 'NTS'),
    ('f1438790', 'Gap in grout', 'NTS'),
    ('8fa8781c', 'Hole in the grout as indicated', 'NTS'),
    ('b3cb1299', 'The plate in the mixer is loose', 'NTS'),
    ('019d6605', 'The plate in the arm is loose', 'NTS'),
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
        SELECT ct.category_name FROM item_template it
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
        WHERE i.cycle_id = ? AND ii.status = 'skipped'
    """, (EXCLUSION_SOURCE_CYCLE,))
    excluded_ids = set(r[0] for r in cur.fetchall())
    print(f"Exclusion template IDs from source cycle: {len(excluded_ids)}")

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
    cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=? AND status=?', (insp_id, 'skipped'))
    print(f"Skipped: {cur.fetchone()[0]} (expected 86)")
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
