"""
Unit 156 Import Script
Block 6, 1st Floor, C1
Inspector: Fisokuhle Matsepe (insp-006)
Date: 2026-02-20
Cycle: 213a746f

64 defects mapped. Kitchen front door items DROPPED (4: door finish, frame hinges, handle, door stop).
Thorough inspector - lots of cleaning items.

Duplicates:
  - 255488c3 (Sink pack hinges) x2
  - 3cb1b144 (Lounge chipped/hollow) x2
  - 04796e27 (Bed A D2 finished) x2
  - afcc1bc2 (Bed A Frame finish) x2
  - b1f2960d (Bed B D2 finished) x3
  - 2ed16ab7 (Bed B chipped/hollow) x2
  - 248d3871 (Bed D paint orchid bay) x2
"""
import sqlite3
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

# ============================================================
# CONFIGURATION
# ============================================================
UNIT_NUMBER = '156'
INSPECTOR_ID = 'insp-006'
INSPECTOR_NAME = 'Fisokuhle Matsepe'
INSPECTION_DATE = '2026-02-20'
TENANT = 'MONOGRAPH'
CYCLE_ID = '213a746f'
EXCLUSION_SOURCE_CYCLE = '213a746f'

# ============================================================
# DEFECTS (template_id, raw_description, defect_type)
# ============================================================
DEFECTS = [
    # KITCHEN - DOORS (1, front door items excluded)
    ('b149d8da', 'Unit signage needs to be cleaned', 'NTS'),

    # KITCHEN - WALLS (2)
    ('16e941da', 'Paint to be cleaned', 'NTS'),
    ('828b90e9', 'Inconsistent grout colour at splash back', 'NTS'),

    # KITCHEN - WINDOWS (2)
    ('065b6eb7', 'W1 frame to be cleaned', 'NTS'),
    ('cbaefabd', 'W1 glass to be cleaned', 'NTS'),

    # KITCHEN - FLOOR (2)
    ('6957702f', 'Grout application is inconsistent', 'NTS'),
    ('3cf49a3d', 'Tile skirting has paint', 'NTS'),

    # KITCHEN - ELECTRICAL (2)
    ('7414ad92', 'DB cover is loose', 'NTS'),
    ('6b89724d', 'Fluorescent light only one bulb working', 'NI'),

    # KITCHEN - PLUMBING (1)
    ('d6dabbc6', 'Sink to be cleaned', 'NTS'),

    # KITCHEN - JOINERY (7, includes 1 duplicate sink pack)
    ('255488c3', 'Sink pack door slightly big making closing hard', 'NTS'),
    ('0c881d18', 'Sink pack top to be cleaned', 'NTS'),
    ('255488c3', 'Sink pack doors hard to close', 'NTS'),
    ('445ab368', 'Bin drawer runners feel stiff', 'NTS'),
    ('197ab3b2', 'Lockable pack 1 and 2 shelf is loose', 'NTS'),
    ('218f3d5a', 'Lockable pack 1 and 2 left lock is loose', 'NTS'),
    ('8ada7164', 'Eye level pack missing screw covers', 'NTS'),

    # LOUNGE (5, includes 1 duplicate floor)
    ('3cb1b144', 'Chipped tiles', 'NTS'),
    ('3cb1b144', 'Hollow tiles', 'NTS'),
    ('feafbe9d', 'Grout application is inconsistent', 'NTS'),
    ('ed852bc0', 'Ceiling mounted light only has one bulb', 'NI'),
    ('fa47bce5', 'Double plug on wall 09 to be cleaned', 'NTS'),

    # BATHROOM (3)
    ('fc632a8a', 'Shadow line recess has cracks', 'NTS'),
    ('051081c5', 'W2 handles have loose screw cover', 'NTS'),
    ('107b77d6', 'Only one light bulb', 'NI'),

    # BEDROOM A (10, includes 2 duplicate pairs)
    ('04796e27', 'Door needs to be painted around handle', 'NTS'),
    ('04796e27', 'Door paint chipped', 'NTS'),
    ('afcc1bc2', 'Frame paint overlaps', 'NTS'),
    ('afcc1bc2', 'Frame finish chipped', 'NTS'),
    ('db6da547', 'W4 frame has paint marks', 'NTS'),
    ('0a294996', 'W4 glass to be cleaned', 'NTS'),
    ('f029f58b', 'W4 burglar bars to be cleaned', 'NTS'),
    ('4b7bbc57', 'W4 window sill to be cleaned', 'NTS'),
    ('e1d9e932', 'Grout application is inconsistent', 'NTS'),
    ('1aeff3ea', 'Double light switch on wall 02 to be cleaned', 'NTS'),

    # BEDROOM B (16, includes 2 duplicate D2 + 1 duplicate floor)
    ('b1f2960d', 'Door not closing well', 'NTS'),
    ('b1f2960d', 'Door paint overlaps', 'NTS'),
    ('b1f2960d', 'Door paint not done well by handle', 'NTS'),
    ('31774738', 'Frame hinges to be repainted', 'NTS'),
    ('340d94a3', 'Frame paint application is not consistent', 'NTS'),
    ('09b9fc9b', 'W3 frame and coating to be cleaned', 'NTS'),
    ('59a35f5a', 'W3 glass to be cleaned', 'NTS'),
    ('d58ea077', 'W3 handle is missing screw covers', 'NTS'),
    ('6348ca23', 'W3 top window is hard to close', 'NTS'),
    ('6e79a407', 'W3 sill to be cleaned', 'NTS'),
    ('2ed16ab7', 'Chipped tile', 'NTS'),
    ('2ed16ab7', 'Hollow tile', 'NTS'),
    ('81520953', 'Grout application inconsistent', 'NTS'),
    ('1136f030', 'Tile skirting chipped', 'NTS'),
    ('a7d14262', 'Chipped paint near WiFi cable entry point', 'NTS'),
    ('a11aff40', 'Panel heater plug on wall 07 is loose', 'NTS'),

    # BEDROOM C (7)
    ('80177e8e', 'Door overlapping paint', 'NTS'),
    ('1fae2eac', 'W3 frame and coating to be cleaned', 'NTS'),
    ('3f2f2146', 'W3 glass to be cleaned', 'NTS'),
    ('4bae57dc', 'W3 handle screw covers are loose', 'NTS'),
    ('f34b4fe9', 'Missing grout', 'NTS'),
    ('6579fac6', 'Ceiling two tone paint', 'NTS'),
    ('968ba64b', 'B.I.C. top shelf is loose', 'NTS'),

    # BEDROOM D (6, includes 1 duplicate walls)
    ('212d83e1', 'Door finish chipped', 'NTS'),
    ('c0183fae', 'Frame hinges have chipped paint', 'NTS'),
    ('66cc0d36', 'Frame finish is chipped', 'NTS'),
    ('248d3871', 'Walls paint is inconsistent', 'NTS'),
    ('248d3871', 'Walls missing paint below window handle', 'NTS'),
    ('bc867a0a', 'W3 handles have no screw covers', 'NTS'),
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
