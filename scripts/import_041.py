"""
Block 6 Import Script - Unit 041
Inspector: Thembinkosi Biko (insp-004)
Inspection Date: 2026-02-03
Defects: 18 NTS + 1 N/I = 19 total
"""
import sqlite3
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

# ============================================================
# CONFIGURATION
# ============================================================
UNIT_NUMBER = '041'
INSPECTOR_ID = 'insp-004'
INSPECTOR_NAME = 'Thembinkosi Biko'
INSPECTION_DATE = '2026-02-03'
TENANT = 'MONOGRAPH'
CYCLE_ID = '36e85327'  # Block 6 cycle

# ============================================================
# DEFECT MAP (confirmed by Johan)
# (area, category_search, item_search, raw_description, defect_type)
# defect_type: NTS = Not to Standard, NI = Not Installed
# ============================================================
DEFECTS = [
    # KITCHEN
    ("KITCHEN", "DOORS", "soft joint",
     "Soft joint has a portion missing along path to Bedroom C", "NTS"),
    ("KITCHEN", "WALLS", "finish",
     "Wall needs to be painted by W1 and by DB", "NTS"),
    ("KITCHEN", "Bin drawer", "runner",
     "Stiff operation", "NTS"),
    ("KITCHEN", "Sink pack", "shelves",
     "Shelf inside has water and is stained, to be cleaned", "NTS"),
    ("KITCHEN", "Sink pack", "hinge",
     "Left door hinge is loose", "NTS"),
    ("KITCHEN", "Eye level pack", "carcass",
     "Paint stains by DB and left door, needs cleaning inside", "NTS"),
    # BATHROOM
    ("BATHROOM", "DOORS", "finish",
     "Stains to be cleaned off door", "NTS"),
    ("BATHROOM", "DOORS", "D3",
     "D3 difficult to open, needs force", "NTS"),
    ("BATHROOM", "WHB", "installation",
     "Cardboard used between WHB and stand to keep balance", "NTS"),
    ("BATHROOM", "WC", "waste",
     "Waste pipe to be installed, water running out of WC", "NTS"),
    # BEDROOM A
    ("BEDROOM A", "WALLS", "finish",
     "Dent under W4", "NTS"),
    # BEDROOM B
    ("BEDROOM B", "B.I.C", "shelf",
     "Plastic shelf supporters inside B.I.C cracked", "NTS"),
    ("BEDROOM B", "Study desk", "fixing",
     "Study desk missing one screw", "NTS"),
    # BEDROOM C
    ("BEDROOM C", "B.I.C", "shelf",
     "Plastic shelf supporters inside B.I.C cracked", "NTS"),
    # BEDROOM D
    ("BEDROOM D", "DOORS", "finish",
     "Dent by door handle", "NTS"),
    ("BEDROOM D", "Ironmongery", "lockset",
     "Lockset cylinder and thumb turn does not lock", "NTS"),
    ("BEDROOM D", "FLOOR", "tile",
     "Tile cracked/chipped by door stop", "NTS"),
    ("BEDROOM D", "B.I.C", "shelf",
     "Plastic shelf supporters inside B.I.C cracked", "NTS"),
    # LOUNGE
    ("LOUNGE", "ELECTRICAL", "Wi-Fi",
     "Wi-Fi Repeater not installed", "NI"),
]

# ============================================================
# HELPER FUNCTIONS
# ============================================================
def gen_id():
    return uuid.uuid4().hex[:8]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def fuzzy_match(text, candidates, threshold=0.6):
    """Find best match from candidates. Returns (match_text, score) or (None, 0)."""
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

def find_template_id(cur, area_name, cat_search, item_search):
    """
    Dynamic template ID lookup using the 3-table join.
    Searches by area name, then filters by category/item keywords.
    """
    cur.execute("""
        SELECT it.id, it.item_name, ct.category_name, at2.area_name
        FROM item_template it
        JOIN category_template ct ON it.category_id = ct.id
        JOIN area_template at2 ON ct.area_id = at2.id
        WHERE at2.area_name LIKE ? AND it.tenant_id = ?
        AND it.parent_item_id IS NOT NULL
    """, (f'%{area_name}%', TENANT))
    rows = cur.fetchall()

    # Score each candidate
    best_id = None
    best_score = 0
    best_name = None
    for row in rows:
        tid, iname, cname, aname = row
        # Both category and item must partially match
        cat_score = SequenceMatcher(None, cat_search.lower(), cname.lower()).ratio()
        item_score = SequenceMatcher(None, item_search.lower(), iname.lower()).ratio()
        # Weighted: item name matters more
        combined = (cat_score * 0.4) + (item_score * 0.6)
        if combined > best_score:
            best_score = combined
            best_id = tid
            best_name = f"{aname} > {cname} > {iname}"

    if best_score < 0.3:
        return None, None, best_score
    return best_id, best_name, best_score

def wash_description(cur, item_template_id, category_name, raw_desc):
    """
    Two-tier defect library wash:
    1. Item-specific matches (item_template_id matches)
    2. Category fallback (item_template_id IS NULL, category matches)
    3. No match = use cleaned raw text + add to library
    Returns (washed_description, match_source)
    """
    # Tier 1: Item-specific
    cur.execute("""
        SELECT description FROM defect_library
        WHERE tenant_id = ? AND item_template_id = ?
        ORDER BY usage_count DESC
    """, (TENANT, item_template_id))
    item_entries = [r[0] for r in cur.fetchall()]

    if item_entries:
        match, score = fuzzy_match(raw_desc, item_entries, threshold=0.5)
        if match:
            return match, f"item-specific (score={score:.2f})"

    # Tier 2: Category fallback
    cur.execute("""
        SELECT description FROM defect_library
        WHERE tenant_id = ? AND category_name = ? AND item_template_id IS NULL
        ORDER BY usage_count DESC
    """, (TENANT, category_name))
    cat_entries = [r[0] for r in cur.fetchall()]

    if cat_entries:
        match, score = fuzzy_match(raw_desc, cat_entries, threshold=0.5)
        if match:
            return match, f"category-fallback (score={score:.2f})"

    # Tier 3: No match - clean up and add to library
    cleaned = raw_desc.strip()
    # Capitalize first letter
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned, "NEW (added to library)"

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

    # --- 1. GET UNIT ---
    cur.execute('SELECT id FROM unit WHERE unit_number=? AND tenant_id=?',
                (UNIT_NUMBER, TENANT))
    row = cur.fetchone()
    if not row:
        print(f"ERROR: Unit {UNIT_NUMBER} not found")
        conn.close()
        return
    unit_id = row[0]
    print(f"Unit ID: {unit_id}")

    # --- 2. CHECK/CREATE INSPECTION ---
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

    # --- 3. UPDATE INSPECTOR ASSIGNMENT ---
    cur.execute("""
        UPDATE inspection SET inspector_id=?, inspector_name=?, updated_at=?
        WHERE id=?
    """, (INSPECTOR_ID, INSPECTOR_NAME, now, insp_id))

    # Update cycle_unit_assignment if exists
    cur.execute("""
        UPDATE cycle_unit_assignment SET inspector_id=?
        WHERE cycle_id=? AND unit_id=?
    """, (INSPECTOR_ID, CYCLE_ID, unit_id))
    print(f"Inspector set: {INSPECTOR_NAME}")

    # --- 4. CREATE INSPECTION ITEMS (all 523) ---
    cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=?', (insp_id,))
    existing_items = cur.fetchone()[0]
    if existing_items > 0:
        print(f"Inspection items already exist: {existing_items}")
    else:
        cur.execute('SELECT id FROM item_template WHERE tenant_id=?', (TENANT,))
        templates = cur.fetchall()
        for t in templates:
            cur.execute("""
                INSERT INTO inspection_item (id, inspection_id, item_template_id, status, marked_at)
                VALUES (?, ?, ?, 'pending', NULL)
            """, (gen_id(), insp_id, t[0]))
        print(f"Created {len(templates)} inspection items")

    # --- 5. MARK EXCLUSIONS (status=skipped) ---
    # Get excluded item template IDs from Block 5 cycle (same exclusions)
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

    # --- 6. MAP DEFECTS + WASH DESCRIPTIONS ---
    print()
    print("--- DEFECT MAPPING + WASH ---")
    mapped_defects = []
    errors = []
    new_library = []

    for i, (area, cat_search, item_search, raw_desc, dtype) in enumerate(DEFECTS, 1):
        template_id, template_path, score = find_template_id(cur, area, cat_search, item_search)
        if not template_id:
            errors.append(f"  #{i}: FAILED to map: {area} > {cat_search} > {item_search} (score={score:.2f})")
            continue

        # Get category name for wash lookup
        cur.execute("""
            SELECT ct.category_name
            FROM item_template it
            JOIN category_template ct ON it.category_id = ct.id
            WHERE it.id = ?
        """, (template_id,))
        cat_row = cur.fetchone()
        cat_name = cat_row[0] if cat_row else cat_search

        # Wash the description
        washed_desc, wash_source = wash_description(cur, template_id, cat_name, raw_desc)

        if "NEW" in wash_source:
            new_library.append((template_id, cat_name, washed_desc))

        mapped_defects.append((template_id, template_path, washed_desc, dtype, wash_source))
        print(f"  #{i}: {template_path}")
        print(f"       Raw: {raw_desc}")
        print(f"       Washed: {washed_desc} [{wash_source}]")

    if errors:
        print()
        print("--- MAPPING ERRORS ---")
        for e in errors:
            print(e)
        print("ABORTING - fix mapping errors before import")
        conn.rollback()
        conn.close()
        return

    # --- 7. CREATE DEFECT RECORDS + MARK NTS ---
    print()
    print("--- CREATING DEFECTS ---")
    defect_count = 0
    for template_id, template_path, washed_desc, dtype, wash_source in mapped_defects:
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

        # Mark inspection item as NTS or not_installed
        item_status = 'not_installed' if dtype == 'NI' else 'not_to_standard'
        cur.execute("""
            UPDATE inspection_item SET status=?, defect_description=?, marked_at=?
            WHERE inspection_id=? AND item_template_id=?
        """, (item_status, washed_desc, now, insp_id, template_id))

        defect_count += 1

    print(f"Defects created: {defect_count}")

    # --- 8. MARK REMAINING AS OK ---
    cur.execute("""
        UPDATE inspection_item SET status='ok', marked_at=?
        WHERE inspection_id=? AND status='pending'
    """, (now, insp_id))
    ok_count = cur.rowcount
    print(f"Marked OK: {ok_count}")

    # --- 9. ADD NEW ENTRIES TO DEFECT LIBRARY ---
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

    # --- 10. SET INSPECTION STATUS ---
    cur.execute("""
        UPDATE inspection SET status='submitted', submitted_at=?, updated_at=?
        WHERE id=?
    """, (now, now, insp_id))

    # --- 11. SET UNIT STATUS ---
    cur.execute("""
        UPDATE unit SET status='in_progress' WHERE id=? AND status='not_started'
    """, (unit_id,))

    # --- 12. VERIFY ---
    print()
    print("=== VERIFICATION ===")
    cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=? AND status=?',
                (insp_id, 'skipped'))
    print(f"Skipped: {cur.fetchone()[0]}")
    cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=? AND status=?',
                (insp_id, 'ok'))
    print(f"OK: {cur.fetchone()[0]}")
    cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=? AND status IN (?,?)',
                (insp_id, 'not_to_standard', 'not_installed'))
    print(f"NTS/NI: {cur.fetchone()[0]}")
    cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=? AND status=?',
                (insp_id, 'pending'))
    print(f"Pending (should be 0): {cur.fetchone()[0]}")
    cur.execute('SELECT COUNT(*) FROM defect WHERE unit_id=? AND raised_cycle_id=? AND status=?',
                (unit_id, CYCLE_ID, 'open'))
    print(f"Defects: {cur.fetchone()[0]}")

    total = 0
    for status in ['skipped', 'ok', 'not_to_standard', 'not_installed', 'pending']:
        cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=? AND status=?',
                    (insp_id, status))
        total += cur.fetchone()[0]
    print(f"Total items: {total} (should be 523)")

    # COMMIT
    conn.commit()
    print()
    print("COMMITTED SUCCESSFULLY")
    conn.close()

if __name__ == '__main__':
    main()
