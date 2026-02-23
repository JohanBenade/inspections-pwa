"""
Unit 155 Import Script
Block 6, 1st Floor, C1
Inspector: Lindokuhle Zulu (insp-005)
Date: 2026-02-20
Cycle: 213a746f

47 defects mapped. Kitchen front door items DROPPED (2).
FF&E items included - exclusion overlap check will handle if excluded.
General notes DROPPED (Wi-Fi, plugs not tested, no water).

Duplicate templates:
  - b1f2960d (Bed B D2 finished all round) x2
  - 80177e8e (Bed C D2 finished all round) x2
  - f1438790 (Bathroom grout dove grey) x2
"""
import sqlite3
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

# ============================================================
# CONFIGURATION
# ============================================================
UNIT_NUMBER = '155'
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
    # KITCHEN - WALLS (1)
    ('16e941da', 'Paint damaged', 'NTS'),

    # KITCHEN - FLOOR (1)
    ('3cf49a3d', 'Grout missing in between tile skirting and floor', 'NTS'),

    # KITCHEN - ELECTRICAL (1)
    ('97cdacb1', 'Stove not turning on', 'NTS'),

    # KITCHEN - JOINERY (3)
    ('5158daf4', 'Sink pack back wall needs to be repainted', 'NTS'),
    ('5fe88982', 'Counter seating leg support is loose', 'NTS'),
    ('7f7ddc15', 'Broom cupboard carcass has no screw covers', 'NTS'),

    # LOUNGE (2)
    ('a46f716d', 'Grout missing in between tile skirting and floor', 'NTS'),
    ('3cb1b144', 'Chipped tile', 'NTS'),

    # BEDROOM A (2)
    ('41c9bd11', 'Chipped tile', 'NTS'),
    ('519d4580', 'Floating shelf loose edge', 'NTS'),

    # BEDROOM B (9)
    ('b1f2960d', 'Door edges not painted', 'NTS'),
    ('b1f2960d', 'Door has grey paint marks', 'NTS'),
    ('340d94a3', 'Frame has paint marks', 'NTS'),
    ('a7d14262', 'Walls paint marks', 'NTS'),
    ('81520953', 'Grout missing in between tiles', 'NTS'),
    ('1136f030', 'Grout on tile skirting has holes', 'NTS'),
    ('b389dfc2', 'Ceiling unpainted patch above blind', 'NTS'),
    ('d58ea077', 'Window top handle to be installed properly', 'NTS'),
    ('7b3e816b', 'Floating shelf loose edge', 'NTS'),

    # BEDROOM C (10)
    ('80177e8e', 'Door overlapping paint', 'NTS'),
    ('80177e8e', 'Door unpainted patches', 'NTS'),
    ('dad5b52a', 'Signage has paint droplets that need to be removed', 'NTS'),
    ('3f2f2146', 'Window broken glass', 'NTS'),
    ('1fae2eac', 'Window has paint droplets', 'NTS'),
    ('85620ac4', 'Chipped tiles', 'NTS'),
    ('6a0771ae', 'Grout missing in between tile skirting and floor', 'NTS'),
    ('981e4097', 'B.I.C. carcass has a white paint patch', 'NTS'),
    ('0b929eb3', 'Floating shelf loose edge', 'NTS'),
    ('fe1f4b2d', 'Towel rail is loose', 'NTS'),

    # BEDROOM D (5)
    ('66cc0d36', 'Frame damaged finish', 'NTS'),
    ('6f905df9', 'Door stop is loose', 'NTS'),
    ('248d3871', 'Walls have oil droplets', 'NTS'),
    ('f653cf83', 'Floating shelf loose edge', 'NTS'),
    ('874c7df6', 'Towel rail is loose', 'NTS'),

    # BATHROOM (13)
    ('e326b993', 'Frame damaged paint', 'NTS'),
    ('f27ee884', 'Frame screws on hinges are damaging the paint finish', 'NTS'),
    ('ebb584a4', 'Pull handle is missing screws', 'NI'),
    ('f1438790', 'Missing grout in between skirting and floor', 'NTS'),
    ('f1438790', 'Grout missing in between tiles', 'NTS'),
    ('ef937d8f', 'Broken tile near WC pipe', 'NTS'),
    ('818a1716', 'Chipped tile', 'NTS'),
    ('107b77d6', 'Ceiling light only has one bulb', 'NI'),
    ('8667f32c', 'WC not flushed to wall', 'NTS'),
    ('019d6605', 'Shower arm loose to wall', 'NTS'),
    ('afa84132', 'Robe hook on shower is loose', 'NTS'),
    ('b4a7d129', 'Robe hook behind door is loose', 'NTS'),
    ('6c44b28e', 'Toilet roll holder is loose', 'NTS'),
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
    print(f"Defects to import: {len(DEFECTS)}")
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
        WHERE i.cycle_id = ? AND ii.status = 'skipped' AND i.id != ?
    """, (CYCLE_ID, insp_id))
    excluded_ids = set(r[0] for r in cur.fetchall())
    print(f"Exclusion template IDs from cycle: {len(excluded_ids)}")

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

    conn.commit()
    print()
    print("COMMITTED SUCCESSFULLY")
    conn.close()

if __name__ == '__main__':
    main()
