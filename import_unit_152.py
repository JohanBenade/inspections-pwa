"""
Unit 152 Import Script
Block 6, 1st Floor, C1
Inspector: Alex Nataniel (team-lead)
Date: 2026-02-20
Cycle: 213a746f

63 defects mapped from Word doc against verified template tree.
Kitchen front door frame defect DROPPED (excluded).
General notes DROPPED (Wi-Fi, plugs not tested, no water, FF&E).

Duplicate templates (2 defects on same template ID):
  - 3cf49a3d (Kitchen tile skirting) x2
  - a1eecb62 (Bed A paint-orchid bay) x2
  - 1136f030 (Bed B tile skirting) x2
  - 4e25adea (Bed C B.I.C. finish) x2
  - 212d83e1 (Bed D D2 finished all round) x2
"""
import sqlite3
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

# ============================================================
# CONFIGURATION
# ============================================================
UNIT_NUMBER = '152'
INSPECTOR_ID = 'team-lead'
INSPECTOR_NAME = 'Alex Nataniel'
INSPECTION_DATE = '2026-02-20'
TENANT = 'MONOGRAPH'
CYCLE_ID = '213a746f'
EXCLUSION_SOURCE_CYCLE = '213a746f'  # B6 1F C1 (same cycle, exclusions already set)

# ============================================================
# DEFECTS (template_id, raw_description, defect_type)
# NTS = Not to Standard, NI = Not Installed
# ============================================================
DEFECTS = [
    # KITCHEN - WALLS (4)
    ('16e941da', 'Peeling paint near double light switch', 'NTS'),
    ('7889a386', 'Tile trim near W1a has hole in grout', 'NTS'),
    ('1d0f508f', 'Wrap at sink not applied well on left side', 'NTS'),
    ('5317757a', 'Tiles under eye level pack no grout', 'NTS'),

    # KITCHEN - FLOOR (3, includes 1 duplicate from misplaced electrical line)
    ('bdafda18', 'Soft joint cross sealant not applied consistently', 'NTS'),
    ('6957702f', 'Inconsistent grout colour', 'NTS'),
    ('3cf49a3d', 'Grout missing in between tile skirting and floor', 'NTS'),

    # KITCHEN - ELECTRICAL (3)
    ('13ec6997', 'Fridge double plug feels loose', 'NTS'),
    ('3cf49a3d', 'Grout missing between tile skirting and floor', 'NTS'),  # dup - misplaced under Electrical
    ('1d0a879b', 'Stove isolator switch is not flushed', 'NTS'),

    # KITCHEN - STOVE (1)
    ('6e557218', 'Stove top is loose', 'NTS'),

    # KITCHEN - JOINERY (9)
    ('5158daf4', 'Sink pack back wall not painted and looks damp', 'NTS'),
    ('255488c3', 'Sink pack hinges are rusted', 'NTS'),
    ('445ab368', 'Bin drawer runners have sand', 'NTS'),
    ('f0fc9699', 'Drawer pack layout is not straight', 'NTS'),
    ('09e5b0d4', 'Counter seating fixing to wall not done well', 'NTS'),
    ('5fe88982', 'Counter seating leg support is loose', 'NTS'),
    ('ddd7b868', 'Lockable pack 1 and 2 hole on back board', 'NTS'),
    ('38b69f7c', 'Eye level pack gap in middle shelf bottom', 'NTS'),
    ('8c97a66a', 'Eye level pack plastic to be removed on handles', 'NTS'),

    # LOUNGE (3)
    ('c248c406', 'Orchid bay paint has dirt', 'NTS'),
    ('feafbe9d', 'Grout has inconsistent colour', 'NTS'),
    ('a46f716d', 'Grout missing in between tile skirting and floor', 'NTS'),

    # BEDROOM A (4, includes 1 duplicate paint)
    ('a1eecb62', 'Mark on wall', 'NTS'),
    ('a1eecb62', 'Not painted well above floating shelf', 'NTS'),
    ('14eb7511', 'Gap between tile skirting and floor', 'NTS'),
    ('dc0e02ee', 'B.I.C. paint marks on the board', 'NTS'),

    # BEDROOM B (5, includes 1 duplicate skirting)
    ('340d94a3', 'Frame damaged finish', 'NTS'),
    ('d58ea077', 'Window handle is loose', 'NTS'),
    ('1136f030', 'Gap between tile skirting and floor', 'NTS'),
    ('1136f030', 'Skirting not straight under B.I.C.', 'NTS'),
    ('7b3e816b', 'Floating shelf loose edge', 'NTS'),

    # BEDROOM C (8, includes 1 duplicate BIC finish)
    ('80177e8e', 'Door not finished well around the handle', 'NTS'),
    ('9fdcd89e', 'Frame finish damaged', 'NTS'),
    ('6a0771ae', 'Gap between tile skirting and floor', 'NTS'),
    ('3c88e688', 'B.I.C. gap between wall', 'NTS'),
    ('4e25adea', 'B.I.C. back wall is not painted well all round', 'NTS'),
    ('4e25adea', 'B.I.C. paint mark', 'NTS'),
    ('0b929eb3', 'Floating shelf loose edge', 'NTS'),
    ('f42cffed', 'Study desk screw not all the way in', 'NTS'),

    # BEDROOM D (9, includes 1 duplicate D2)
    ('212d83e1', 'Door damaged paint', 'NTS'),
    ('212d83e1', 'Door white paint marks', 'NTS'),
    ('66cc0d36', 'Frame uneven paint application', 'NTS'),
    ('9d6fe4a5', 'Ironmongery screw is loose', 'NTS'),
    ('4a354d81', 'Window no screw covers', 'NI'),
    ('956b6837', 'Missing grout', 'NTS'),
    ('54ac6a45', 'Poor tile work throughout bedroom', 'NTS'),
    ('f653cf83', 'Floating shelf loose edge', 'NTS'),
    ('b38587a1', 'Study desk 1 screw missing to wall', 'NTS'),

    # BATHROOM - DOORS (3)
    ('b6b5d166', 'Door D2a holes and cracked near lockset', 'NTS'),
    ('e326b993', 'Frame paint is damaged', 'NTS'),
    ('a6939da2', 'D3 magnet strip holds door when opening', 'NTS'),

    # BATHROOM - WALLS (4)
    ('df84942f', 'Tile duct trim has hole', 'NTS'),
    ('76c93f42', 'Tile into window sill has gap in sealant', 'NTS'),
    ('347c7f63', 'Tile trim on window missing grout at top left edge', 'NTS'),
    ('ef937d8f', 'Broken tile near WC pipe', 'NTS'),

    # BATHROOM - WINDOWS (1)
    ('e2528889', 'Gasket not cut at the edge', 'NTS'),

    # BATHROOM - FLOOR (2)
    ('818a1716', 'Chipped tile near door stopper', 'NTS'),
    ('d5c6a122', 'Grout in shower does not look dark', 'NTS'),

    # BATHROOM - ELECTRICAL (1)
    ('107b77d6', 'Ceiling light only has one bulb', 'NI'),

    # BATHROOM - PLUMBING (3)
    ('8667f32c', 'WC not flushed to wall', 'NTS'),
    ('52d96bc1', 'Shut off valve cold cannot be turned', 'NTS'),
    ('d21c5759', 'Shut off valve hot cannot be turned', 'NTS'),
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
