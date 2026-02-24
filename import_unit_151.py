"""
Unit 151 Import Script - B6 1st Floor C1
Inspector: Lindokuhle Zulu (insp-005)
Date: 2026-02-20
Cycle: 213a746f
103 defects mapped from Word doc, 2 pre-dropped (front door)
"""
import sqlite3
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

# ============================================================
# CONFIGURATION
# ============================================================
UNIT_NUMBER = '151'
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
    ('17ff0a59', 'Striker plate does not allow the door handle to close', 'NTS'),
    ('16e941da', 'Paint is chipped and has dirt marks as indicated', 'NTS'),
    ('7889a386', 'Gap between tile trim and tile at window 1a as indicated', 'NTS'),
    ('e4bb8e59', 'Dirt mark in the window sill as indicated', 'NTS'),
    ('1d0f508f', 'Splash back wrap at sink is peeling as indicated', 'NTS'),
    ('828b90e9', 'Gap in the grout as indicated', 'NTS'),
    ('637c7b25', 'Gap between tile trim and the tile', 'NTS'),
    ('5317757a', 'Gap in grout as indicated', 'NTS'),
    ('82751f2d', 'Hinges are beginning to rust', 'NTS'),
    ('0740d3f1', 'Gasket is not applied completely', 'NTS'),
    ('bfc0e3ab', 'Frame has paint marks as indicated', 'NTS'),
    ('707304a2', 'Glass is broken as indicated', 'NTS'),
    ('8ab50f6a', 'Hinges are making a sound and make window difficult to close', 'NTS'),
    ('e49da716', 'Gasket is not applied completely', 'NTS'),
    ('0b7ae206', 'The window is hard to close', 'NTS'),
    ('bdafda18', 'Soft joint application is not consistent as indicated', 'NTS'),
    ('6957702f', 'Gap in grout as indicated', 'NTS'),
    ('3cf49a3d', 'Gap between tile skirting and the floor', 'NTS'),
    ('3cf49a3d', 'Gap between tile skirting and stove lockable', 'NTS'),
    ('7414ad92', 'DB is not flushed to wall, and it has paint marks', 'NTS'),
    ('6e557218', 'Stove needs to be cleaned', 'NTS'),
    ('5158daf4', 'Carcass is chipped and not to standard as indicated', 'NTS'),
    ('0c881d18', 'Top is not smooth as indicated', 'NTS'),
    ('445ab368', 'There is sand in the runners', 'NTS'),
    ('2976f40b', 'Top is not smooth as indicated', 'NTS'),
    ('543d889f', 'Fixing to wall is not to standard', 'NTS'),
    ('2b85b587', 'Carcass is not to standard', 'NTS'),
    ('0ae68663', 'Hinges are missing screws as indicated', 'NTS'),
    ('09e5b0d4', 'Fixing to wall is not to standard', 'NTS'),
    ('5fe88982', 'Leg support is not stable', 'NTS'),
    ('197ab3b2', 'Shelves are not straight', 'NTS'),
    ('38b69f7c', 'Carcass is scratched as indicated', 'NTS'),
    ('8ada7164', 'Finish has paint mark as indicated', 'NTS'),
    # LOUNGE
    ('3cb1b144', 'Chipped tile as indicated', 'NTS'),
    ('a46f716d', 'Gap between tile skirting and the floor', 'NTS'),
    ('a4163cb8', 'Crack in plaster recess', 'NTS'),
    ('ed852bc0', 'There is only one light bulb', 'NTS'),
    # BEDROOM A
    ('2b8649e7', 'Paint on outside is chipped as indicated', 'NTS'),
    ('afcc1bc2', 'Finish has overlapping paint and is scratched', 'NTS'),
    ('212cf40b', 'Screws in frame need to be removed', 'NTS'),
    ('01a96116', 'Paint on outside is chipped as indicated', 'NTS'),
    ('a1eecb62', 'Paint orchid bay has dirty marks', 'NTS'),
    ('4c05e67d', 'Gap in plaster recess', 'NTS'),
    ('14eb7511', 'Gap between tile skirting and the floor', 'NTS'),
    ('1aeff3ea', 'Double light switch on wall 02 has paint marks', 'NTS'),
    ('87c623cb', 'Inconsistent painting in carcass back wall', 'NTS'),
    ('ed43d43a', 'There is a missing screw', 'NTS'),
    ('d9b6f2ac', 'Remove plastic in carcass', 'NTS'),
    # BEDROOM B
    ('b1f2960d', 'Door finish has paint marks at the top of the door', 'NTS'),
    ('5793d608', 'Paint on outside is chipped as indicated', 'NTS'),
    ('622ed9f0', 'Screws on the frame needs to be removed', 'NTS'),
    ('8b80d8a5', 'Paint on outside is chipped as indicated', 'NTS'),
    ('a7d14262', 'Paint orchid bay is chipped and scratched as indicated', 'NTS'),
    ('a7d14262', 'Paint has marks as indicated', 'NTS'),
    ('6348ca23', 'Hinges have rust', 'NTS'),
    ('2ed16ab7', 'Chipped tiles as indicated', 'NTS'),
    ('1136f030', 'Gap between tile skirting and the floor', 'NTS'),
    ('3b44bd96', 'Has a loose screw', 'NTS'),
    # BEDROOM C
    ('80177e8e', 'The painting is inconsistent as indicated', 'NTS'),
    ('9fdcd89e', 'Finish is chipped as indicated', 'NTS'),
    ('24dfa887', 'Paint on outside needs to be cleaned', 'NTS'),
    ('5628303a', 'Paint has dirt marks', 'NTS'),
    ('5628303a', 'Inconsistent paint application as indicated', 'NTS'),
    ('1fae2eac', 'Frame needs to be cleaned', 'NTS'),
    ('3f2f2146', 'Glass needs to be cleaned', 'NTS'),
    ('8ed179fe', 'Hinges have sand', 'NTS'),
    ('13960def', 'Gasket needs to be cleaned', 'NTS'),
    ('85620ac4', 'Chipped tile as indicated', 'NTS'),
    ('f34b4fe9', 'Grout has paint as indicated', 'NTS'),
    ('c57a6bb2', 'Double light switch on wall 24 is not flushed to wall', 'NTS'),
    ('0b929eb3', 'Floating shelf not flushed to B.I.C', 'NTS'),
    ('6ba3e495', 'Screw is not all the way in', 'NTS'),
    # BEDROOM D
    ('45dd2301', 'Paint on outside is chipped as indicated', 'NTS'),
    ('6e2d53af', 'Screws need to be removed', 'NTS'),
    ('66cc0d36', 'There is overlapping paint as indicated', 'NTS'),
    ('3b18b7d5', 'Paint on outside is chipped as indicated', 'NTS'),
    ('248d3871', 'Paint is scratched as indicated', 'NTS'),
    ('8638d78f', 'Hinges are beginning to rust as indicated', 'NTS'),
    ('54ac6a45', 'Chipped tiles as indicated', 'NTS'),
    ('a39a8899', 'Gap between tile skirting and the floor as indicated', 'NTS'),
    ('b1b7e7ec', 'Study desk light screw is not all the way in', 'NTS'),
    ('afe6b938', 'Combination plug wall 19 has paint marks', 'NTS'),
    ('f653cf83', 'Floating shelf not flushed to B.I.C', 'NTS'),
    ('703b89ce', 'Screw is not all the way in as indicated', 'NTS'),
    # BATHROOM
    ('a9c136be', 'Door rubs the frame when closing', 'NTS'),
    ('b6b5d166', 'Finish has paint marks as indicated', 'NTS'),
    ('e326b993', 'Finish is chipped as indicated', 'NTS'),
    ('6f84fade', 'Screws on the frame need to be removed', 'NTS'),
    ('39fe1eda', 'WC indicator bolt and thumb turn is not working', 'NTS'),
    ('a6939da2', 'D3 hard to open', 'NTS'),
    ('f1438790', 'Grout is missing as indicated', 'NTS'),
    ('ef937d8f', 'Chipped tiles as indicated', 'NTS'),
    ('07d644a5', 'Frame is not straight', 'NTS'),
    ('0514ada9', 'Glass needs to be cleaned', 'NTS'),
    ('e2528889', 'Gasket needs to be cleaned', 'NTS'),
    ('818a1716', 'Chipped tile as indicated', 'NTS'),
    ('faea42ac', 'Has dirt spots above window', 'NTS'),
    ('107b77d6', 'Only one light bulb', 'NTS'),
    ('8667f32c', 'WC not flushed to wall', 'NTS'),
    ('b9805e6c', 'Shut off valve plate is loose', 'NTS'),
    ('4d5f2168', 'Shower mixer plate is loose', 'NTS'),
    ('019d6605', 'Arm is loose', 'NTS'),
    ('a9e99c5e', 'Shut off valve cold plate is loose', 'NTS'),
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

    conn.commit()
    print()
    print("COMMITTED SUCCESSFULLY")
    conn.close()

if __name__ == '__main__':
    main()
