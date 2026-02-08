"""
Block 6 Import Script - Unit 045
37 defects (36 NTS + 1 NI), door closer and towel rail may be dropped by exclusion check
"""
import sqlite3
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

UNIT_NUMBER = '045'
INSPECTOR_ID = 'insp-004'
INSPECTOR_NAME = 'Thembinkosi Biko'
INSPECTION_DATE = '2026-02-03'
TENANT = 'MONOGRAPH'
CYCLE_ID = '36e85327'

DEFECTS = [
    # KITCHEN (10)
    ('e1357d91', 'Door closer to be connected', 'NTS'),
    ('3cf49a3d', 'Tile skirting not flushed legibly to cupboard underside and does not connect tiles well at corner', 'NTS'),
    ('16e941da', 'Wall needs to be painted near door', 'NTS'),
    ('197ab3b2', 'Stove wire needs to be secured well', 'NTS'),
    ('2b85b587', 'Needs to be cleaned inside', 'NTS'),
    ('09e5b0d4', 'Not fixed legibly to wall as indicated', 'NTS'),
    ('8ada7164', 'Yellow paint stain inside left pack', 'NTS'),
    ('38b69f7c', 'Chipped inside same pack', 'NTS'),
    ('7f7ddc15', 'Needs to be cleaned inside', 'NTS'),
    ('663cc471', 'Towel rail is loose', 'NTS'),
    # BATHROOM (6)
    ('c16fbe1e', 'Bathroom lock does not lock', 'NTS'),
    ('ef937d8f', 'Chipped tile on wall as indicated', 'NTS'),
    ('07d644a5', 'Corners are rusting', 'NTS'),
    ('2879d87d', 'WC seat not installed', 'NI'),
    ('b3cb1299', 'Mixer plate loose', 'NTS'),
    ('1beaecc9', 'Rose plate loose', 'NTS'),
    # BEDROOM A (3)
    ('e6f434e1', 'Chipped under window and by light switch', 'NTS'),
    ('db6da547', 'Loose hanging screw by right window', 'NTS'),
    ('03e99050', 'Study desk missing one screw', 'NTS'),
    # BEDROOM B (5)
    ('80f75409', 'Handle does not kick back to place', 'NTS'),
    ('d1bfc830', 'Dents on wall under floating shelf', 'NTS'),
    ('1136f030', 'Tile skirting not legibly fixed to B.I.C underside', 'NTS'),
    ('1eb374be', 'Plastic shelf supporters inside B.I.C is cracked', 'NTS'),
    ('5d1dc2bd', 'Study desk missing one screw', 'NTS'),
    # BEDROOM C (7)
    ('9fdcd89e', 'Dusty white stain above door', 'NTS'),
    ('c2e3219c', 'Handle does not kick back to place', 'NTS'),
    ('80177e8e', 'Screw like rubber studs damaging door finish to be removed', 'NTS'),
    ('968ba64b', 'Plastic shelf supporters cracked due to being screwed in too much', 'NTS'),
    ('5628303a', 'Green paint stains on orchid bay paint', 'NTS'),
    ('6a0771ae', 'Not well finished to underside', 'NTS'),
    ('f42cffed', 'Loose screws as indicated', 'NTS'),
    # BEDROOM D (6)
    ('c0183fae', 'Door does not close at all', 'NTS'),
    ('212d83e1', 'Edges are damaged as indicated', 'NTS'),
    ('212d83e1', 'Screw-like rubber stud damaging door finish', 'NTS'),
    ('54ac6a45', 'Chipped tile as indicated', 'NTS'),
    ('b38587a1', 'X1 screw hanging loose', 'NTS'),
    ('4e65f3e9', 'Plastic shelf supporters inside B.I.C is cracked', 'NTS'),
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
