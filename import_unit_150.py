"""
Unit 150 Import Script - B6 1st Floor C1
Inspector: Lindokuhle Zulu (insp-005)
Date: 2026-02-20
Cycle: 213a746f
71 defects mapped from Word doc, 5 pre-dropped (4 front door, 1 panel heater FF&E)
"""
import sqlite3
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

# ============================================================
# CONFIGURATION
# ============================================================
UNIT_NUMBER = '150'
INSPECTOR_ID = 'insp-005'
INSPECTOR_NAME = 'Lindokuhle Zulu'
INSPECTION_DATE = '2026-02-20'
TENANT = 'MONOGRAPH'
CYCLE_ID = '213a746f'
EXCLUSION_SOURCE_CYCLE = '213a746f'

# ============================================================
# DEFECTS (template_id, raw_description, defect_type)
# ============================================================
DEFECTS = [
    # KITCHEN
    ('e4bb8e59', 'Gap between tile trim and tile in window sill as indicated', 'NTS'),
    ('485aba2b', 'Tile trim is not straight at sink splash back as indicated', 'NTS'),
    ('2aefb106', 'Chipped tiles as indicated', 'NTS'),
    ('637c7b25', 'Tile trim has paint marks as indicated', 'NTS'),
    ('76477531', 'Chipped tile as indicated', 'NTS'),
    ('cbaefabd', 'Glass needs to be cleaned', 'NTS'),
    ('8ab50f6a', 'There is sand in the hinges', 'NTS'),
    ('522b4aeb', 'Chipped tile near door stop as indicated', 'NTS'),
    ('6957702f', 'There is a hole in the grout as indicated', 'NTS'),
    ('3cf49a3d', 'Gap between tile skirting and the floor', 'NTS'),
    ('3cf49a3d', 'Gap between tile skirting and joineries', 'NTS'),
    ('6eb3af36', 'There is a crack in the plaster recess', 'NTS'),
    ('5158daf4', 'Carcass needs to be painted as indicated', 'NTS'),
    ('255488c3', 'There is rust in the hinges as indicated', 'NTS'),
    ('624544cd', 'Carcass needs to be cleaned', 'NTS'),
    ('ff38c47c', 'The runners in the last drawer stucks as indicated', 'NTS'),
    ('09e5b0d4', 'Fixing to wall is not to standard', 'NTS'),
    ('5fe88982', 'Leg support is not stable', 'NTS'),
    ('ddd7b868', 'Carcass is chipped as indicated', 'NTS'),
    ('4ff599bf', 'Hinge is not flushed as indicated', 'NTS'),
    # LOUNGE
    ('c248c406', 'Paint is chipped as indicated', 'NTS'),
    ('3cb1b144', 'Chipped tiles as indicated', 'NTS'),
    ('feafbe9d', 'Gaps in grout as indicated', 'NTS'),
    ('a46f716d', 'Gaps between tile skirting and the floor as indicated', 'NTS'),
    ('ed852bc0', 'There is only one light bulb', 'NTS'),
    ('fa47bce5', 'Double plug on 09 wall is not flushed to the wall', 'NTS'),
    # BEDROOM A
    ('04796e27', 'Door rubs the floor when closing', 'NTS'),
    ('afcc1bc2', 'Overlapping paint as indicated', 'NTS'),
    ('a1eecb62', 'Paint orchid bay has paint marks as indicated', 'NTS'),
    ('db6da547', 'Frame needs to be cleaned', 'NTS'),
    ('1dda5625', 'Hinges need to be cleaned', 'NTS'),
    ('41c9bd11', 'Chipped tile as indicated', 'NTS'),
    ('14eb7511', 'Gap between tile skirting and the floor', 'NTS'),
    ('14eb7511', 'Gap between tile skirting and B.I.C underside', 'NTS'),
    ('dc0e02ee', 'Finish has paint marks as indicated', 'NTS'),
    ('519d4580', 'Floating shelf not flushed to wall', 'NTS'),
    # BEDROOM B
    ('a7d14262', 'Paint orchid bay has dirt marks as indicated', 'NTS'),
    ('a7d14262', 'Chipped as indicated', 'NTS'),
    ('6348ca23', 'There is rust on the hinges', 'NTS'),
    ('2ed16ab7', 'Chipped tile as indicated', 'NTS'),
    ('1136f030', 'Gap between tile skirting and the floor', 'NTS'),
    ('1136f030', 'Gap between tile skirting and B.I.C underside', 'NTS'),
    # BEDROOM C
    ('9fdcd89e', 'Finish is chipped as indicated', 'NTS'),
    ('85620ac4', 'Chipped tile as indicated', 'NTS'),
    ('6a0771ae', 'Gap between tile skirting and the floor', 'NTS'),
    ('6a0771ae', 'Gap between tile skirting and B.I.C underside', 'NTS'),
    ('6ba3e495', 'There is a missing screw', 'NTS'),
    ('6ba3e495', 'Carcass has paint marks', 'NTS'),
    # BEDROOM D
    ('66cc0d36', 'Finish is chipped as indicated', 'NTS'),
    ('9d6fe4a5', 'Residence lock handle screw is not all the way in', 'NTS'),
    ('248d3871', 'Paint orchid bay has dirt marks as indicated', 'NTS'),
    ('248d3871', 'Overlapping paint as indicated', 'NTS'),
    ('a39a8899', 'Gap between tile skirting and the floor', 'NTS'),
    ('a39a8899', 'Gap between tile skirting and B.I.C underside', 'NTS'),
    ('a39a8899', 'Tile skirting tile is chipped as indicated', 'NTS'),
    ('700c338e', 'Panel heater plug wall 20 is not flushed to wall', 'NTS'),
    ('263b99ba', 'Paint in carcass is chipped as indicated', 'NTS'),
    ('263b99ba', 'Carcass has a screw', 'NTS'),
    # BATHROOM
    ('b6b5d166', 'Finish is chipped as indicated', 'NTS'),
    ('39fe1eda', 'WC indicator bolt and thumb turn is not working', 'NTS'),
    ('3016c121', 'Gap between tile trim and tile on the shower step', 'NTS'),
    ('df84942f', 'Gap between tile trim and tile on the duct wall corner', 'NTS'),
    ('347c7f63', 'Gap between tile trim and tile on window reveal', 'NTS'),
    ('f1438790', 'Gaps in grout', 'NTS'),
    ('ef937d8f', 'Tile cut as indicated', 'NTS'),
    ('818a1716', 'Chipped tile as indicated', 'NTS'),
    ('107b77d6', 'There is only one light bulb', 'NTS'),
    ('8667f32c', 'WC not flushed to wall', 'NTS'),
    ('4d5f2168', 'Shower mixer plate is loose', 'NTS'),
    ('a9e99c5e', 'Shut off valve cold plate is loose', 'NTS'),
    ('e5372c9d', 'Shut off valve hot plate is loose', 'NTS'),
]

# ============================================================
# HELPER FUNCTIONS
# ============================================================
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

    # Tier 1: Item-specific
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

    # Tier 2: Category fallback
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

    # Tier 3: No match - clean up raw text
    cleaned = raw_desc.strip()
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned, "NEW (added to library)", cat_name

# ============================================================
# MAIN IMPORT
# ============================================================
def main():
    conn = sqlite3.connect('/var/data/inspections.db')
    cur = conn.cursor()
    now = now_iso()

    print(f"=== IMPORT: Unit {UNIT_NUMBER} ===")
    print(f"Inspector: {INSPECTOR_NAME} ({INSPECTOR_ID})")
    print(f"Date: {INSPECTION_DATE}")
    print(f"Cycle: {CYCLE_ID}")
    print()

    # --- 1. VERIFY TEMPLATE IDs EXIST ---
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

    # --- 2. GET UNIT ---
    cur.execute('SELECT id FROM unit WHERE unit_number=? AND tenant_id=?',
                (UNIT_NUMBER, TENANT))
    row = cur.fetchone()
    if not row:
        print(f"ERROR: Unit {UNIT_NUMBER} not found")
        conn.close()
        return
    unit_id = row[0]
    print(f"Unit ID: {unit_id}")

    # --- 3. CHECK/CREATE INSPECTION ---
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

    # --- 4. UPDATE INSPECTOR ASSIGNMENT ---
    cur.execute("""
        UPDATE inspection SET inspector_id=?, inspector_name=?, updated_at=?
        WHERE id=?
    """, (INSPECTOR_ID, INSPECTOR_NAME, now, insp_id))
    cur.execute("""
        UPDATE cycle_unit_assignment SET inspector_id=?
        WHERE cycle_id=? AND unit_id=?
    """, (INSPECTOR_ID, CYCLE_ID, unit_id))
    print(f"Inspector set: {INSPECTOR_NAME}")

    # --- 5. CREATE INSPECTION ITEMS (all 523) ---
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

    # --- 6. MARK EXCLUSIONS (status=skipped) ---
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

    # --- 7. CHECK EXCLUSION OVERLAPS ---
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

    # --- 8. WASH DESCRIPTIONS + CREATE DEFECTS ---
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

        # Create defect record
        defect_id = gen_id()
        defect_type = 'not_installed' if dtype == 'NI' else 'not_to_standard'
        cur.execute("""
            INSERT INTO defect
            (id, tenant_id, unit_id, item_template_id, raised_cycle_id,
             defect_type, status, original_comment, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, ?)
        """, (defect_id, TENANT, unit_id, template_id, CYCLE_ID,
              defect_type, washed_desc, now, now))

        # Mark inspection item
        item_status = 'not_installed' if dtype == 'NI' else 'not_to_standard'
        cur.execute("""
            UPDATE inspection_item SET status=?, comment=?, marked_at=?
            WHERE inspection_id=? AND item_template_id=?
        """, (item_status, washed_desc, now, insp_id, template_id))

        defect_count += 1

    print(f"\nDefects created: {defect_count}")

    # --- 9. MARK REMAINING AS OK ---
    cur.execute("""
        UPDATE inspection_item SET status='ok', marked_at=?
        WHERE inspection_id=? AND status='pending'
    """, (now, insp_id))
    ok_count = cur.rowcount
    print(f"Marked OK: {ok_count}")

    # --- 10. ADD NEW ENTRIES TO DEFECT LIBRARY ---
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

    # --- 11. SET INSPECTION STATUS ---
    cur.execute("""
        UPDATE inspection SET status='submitted', submitted_at=?, updated_at=?
        WHERE id=?
    """, (now, now, insp_id))

    # --- 12. SET UNIT STATUS ---
    cur.execute("""
        UPDATE unit SET status='in_progress' WHERE id=? AND status='not_started'
    """, (unit_id,))

    # --- 13. VERIFY ---
    print()
    print("=== VERIFICATION ===")
    cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=? AND status=?',
                (insp_id, 'skipped'))
    print(f"Skipped: {cur.fetchone()[0]} (expected 86)")
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

    # COMMIT
    conn.commit()
    print()
    print("COMMITTED SUCCESSFULLY")
    conn.close()

if __name__ == '__main__':
    main()
