"""
Unit 148 Import - Block 6 1st Floor C1
Inspector: Fisokuhle Matsepe (insp-006)
Date: 2026-02-20
Cycle: 213a746f (B6 1st Floor C1, 86 exclusions)

STANDARD DROPS (pre-filtered - NOT in defect list):
  - Wi-Fi repeater not installed (exclusion)
  - Plugs not tested (not a defect)
  - No water from shower (not a defect)
  - Kitchen front door items (exclusion check handles)
"""
import sqlite3
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

UNIT_NUMBER = '148'
INSPECTOR_ID = 'insp-006'
INSPECTOR_NAME = 'Fisokuhle Matsepe'
INSPECTION_DATE = '2026-02-20'
TENANT = 'MONOGRAPH'
CYCLE_ID = '213a746f'
DRY_RUN = False  # Aborts on any unresolved template

def gen_id():
    return uuid.uuid4().hex[:8]

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def fuzzy(a, b):
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()

def wash_description(cur, item_template_id, raw_desc):
    cur.execute("""SELECT ct.category_name FROM item_template it
        JOIN category_template ct ON it.category_id = ct.id WHERE it.id = ?""",
        (item_template_id,))
    cat_row = cur.fetchone()
    cat_name = cat_row[0] if cat_row else 'UNKNOWN'
    # Tier 1: Item-specific
    cur.execute("SELECT description FROM defect_library WHERE tenant_id=? AND item_template_id=? ORDER BY usage_count DESC",
                (TENANT, item_template_id))
    for r in cur.fetchall():
        if fuzzy(raw_desc, r[0]) >= 0.7:
            return r[0], cat_name
    # Tier 2: Category fallback
    cur.execute("SELECT description FROM defect_library WHERE tenant_id=? AND category_name=? AND item_template_id IS NULL ORDER BY usage_count DESC",
                (TENANT, cat_name))
    for r in cur.fetchall():
        if fuzzy(raw_desc, r[0]) >= 0.7:
            return r[0], cat_name
    cleaned = raw_desc.strip()
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned, cat_name

def resolve_template(cur, area, category, parent_kw, item_kw):
    """Resolve template ID from area/category/parent/item keywords."""
    cur.execute("""
        SELECT c.id, c.item_description, COALESCE(p.item_description, '') as pdesc
        FROM item_template c
        LEFT JOIN item_template p ON c.parent_item_id = p.id
        JOIN category_template ct ON c.category_id = ct.id
        JOIN area_template at2 ON ct.area_id = at2.id
        WHERE c.tenant_id = ? AND c.depth > 0
        AND at2.area_name = ? AND ct.category_name = ?
    """, (TENANT, area, category))
    rows = cur.fetchall()
    if not rows:
        return None, 0, 'NO ROWS for %s > %s' % (area, category)

    best = None
    best_score = 0
    best_info = ''
    for tid, item_desc, parent_desc in rows:
        # Exact substring match gets highest score
        p_exact = 1.0 if parent_kw.lower() in parent_desc.lower() else fuzzy(parent_kw, parent_desc)
        i_exact = 1.0 if item_kw.lower() in item_desc.lower() else fuzzy(item_kw, item_desc)
        score = p_exact * 0.35 + i_exact * 0.65
        if score > best_score:
            best_score = score
            best = tid
            best_info = '%s > %s' % (parent_desc or '(root)', item_desc)
    return best, best_score, best_info


# ============================================================
# DEFECT LIST - mapped from Word doc parse
# (area, category, parent_keyword, item_keyword, raw_description, type)
# ============================================================
DEFECTS = [
    # KITCHEN (3 door/frame items will be caught by exclusion check)
    ('KITCHEN', 'WALLS', 'Wall tile', 'finish', 'Paint chipped as indicated', 'NTS'),
    ('KITCHEN', 'WINDOWS', 'W1', 'glass', 'Glass to be cleaned', 'NTS'),
    ('KITCHEN', 'WINDOWS', 'W1', 'sill', 'Sill to be cleaned and painted', 'NTS'),
    ('KITCHEN', 'WINDOWS', 'W1a', 'glass', 'Glass and sill to be cleaned', 'NTS'),
    ('KITCHEN', 'FLOOR', 'Floor tile', 'grout', 'Grout missing/inconsistent near door as indicated', 'NTS'),
    ('KITCHEN', 'ELECTRICAL', 'DB board', 'screws', 'DB has missing screws', 'NTS'),
    ('KITCHEN', 'JOINERY', 'Bin drawer', 'runner', 'Sand in the runners', 'NTS'),
    ('KITCHEN', 'JOINERY', 'Lockable pack 3&4', 'locks', 'Left lock is loose', 'NTS'),
    ('KITCHEN', 'JOINERY', 'Counter seating', 'leg support', 'Leg support is loose', 'NTS'),
    ('KITCHEN', 'JOINERY', 'Lockable pack 1&2', 'locks', 'Left lock loose', 'NTS'),
    ('KITCHEN', 'JOINERY', 'Towel rail', 'installation', 'Towel rail loose to wall', 'NTS'),
    # LOUNGE
    ('LOUNGE', 'ELECTRICAL', 'Ceiling light', 'bulb', 'Ceiling mounted light only has one bulb', 'NTS'),
    # BATHROOM
    ('BATHROOM', 'DOORS', 'D2', 'finished all round', 'Door to be cleaned', 'NTS'),
    ('BATHROOM', 'WALLS', 'Wall tile', 'grout', 'Grout near frame is inconsistent', 'NTS'),
    ('BATHROOM', 'DOORS', 'Ironmongery', 'lockset', 'Bathroom lock hard to operate and lock', 'NTS'),
    ('BATHROOM', 'WALLS', 'Wall tile', 'grout', 'Grout inconsistent as indicated', 'NTS'),
    ('BATHROOM', 'WALLS', 'Wall tile', 'finish', 'Tile chipped as indicated', 'NTS'),
    ('BATHROOM', 'WALLS', 'Shadow line', 'finish', 'Shadow line recess inconsistent near shower', 'NTS'),
    ('BATHROOM', 'WALLS', 'Wall tile', 'finish', 'Chipped tile near WC shut off valve', 'NTS'),
    ('BATHROOM', 'WINDOWS', 'W5', 'glass', 'Glass to be cleaned', 'NTS'),
    ('BATHROOM', 'WINDOWS', 'W5', 'sill', 'Sill to be cleaned', 'NTS'),
    ('BATHROOM', 'ELECTRICAL', 'Ceiling light', 'bulb', 'Only one light bulb', 'NTS'),
    # BEDROOM A
    ('BEDROOM A', 'DOORS', 'D3', 'finished all round', 'Chipped paint as indicated', 'NTS'),
    ('BEDROOM A', 'DOORS', 'D3', 'finished all round', 'Paint overlaps as indicated', 'NTS'),
    ('BEDROOM A', 'DOORS', 'Frame', 'hinges', 'Hinges have chipped paint', 'NTS'),
    ('BEDROOM A', 'DOORS', 'Frame', 'finish', 'Finish to be cleaned', 'NTS'),
    ('BEDROOM A', 'DOORS', 'Ironmongery', 'lockset', 'Lockset cylinder and thumb turn hard to lock', 'NTS'),
    ('BEDROOM A', 'DOORS', 'Signage', 'installed', 'Signage loose', 'NTS'),
    ('BEDROOM A', 'WINDOWS', 'W2', 'sill', 'Window sill to be cleaned', 'NTS'),
    # BEDROOM B
    ('BEDROOM B', 'DOORS', 'Frame', 'finish', 'Finish has chipped paint as indicated', 'NTS'),
    ('BEDROOM B', 'DOORS', 'Ironmongery', 'handle', 'Lock handle is missing screws', 'NTS'),
    ('BEDROOM B', 'WINDOWS', 'W3', 'handle', 'Handles missing screw covers', 'NTS'),
    ('BEDROOM B', 'WINDOWS', 'W3', 'sill', 'Sill to be cleaned', 'NTS'),
    ('BEDROOM B', 'CEILING', 'Ceiling', 'finish', 'Hole on ceiling as indicated', 'NTS'),
    ('BEDROOM B', 'ELECTRICAL', 'Study desk light', 'screws', 'Screw loose by study desk light', 'NTS'),
    ('BEDROOM B', 'JOINERY', 'Study desk', 'screws', 'Screw not all the way in', 'NTS'),
    # BEDROOM C
    ('BEDROOM C', 'DOORS', 'Frame', 'hinges', 'Hinges to be repainted', 'NTS'),
    ('BEDROOM C', 'DOORS', 'Signage', 'installed', 'Signage to be cleaned', 'NTS'),
    ('BEDROOM C', 'JOINERY', 'Study desk', 'screws', 'Screw not all the way in', 'NTS'),
    # BEDROOM D
    ('BEDROOM D', 'DOORS', 'D3', 'finished all round', 'Finish not consistent', 'NTS'),
    ('BEDROOM D', 'DOORS', 'D3', 'finished all round', 'Paint not well done', 'NTS'),
    ('BEDROOM D', 'DOORS', 'Frame', 'finish', 'Paint work not consistent', 'NTS'),
    ('BEDROOM D', 'DOORS', 'Ironmongery', 'handle', 'Lock handle missing screws', 'NTS'),
    ('BEDROOM D', 'WALLS', 'Floating shelf', 'finish', 'Paint not consistent by floating shelf', 'NTS'),
    ('BEDROOM D', 'WALLS', 'Wall', 'finish', 'Chipped wall by combination plug', 'NTS'),
    ('BEDROOM D', 'WINDOWS', 'W4', 'frame', 'Frame chipped as indicated', 'NTS'),
    ('BEDROOM D', 'JOINERY', 'B.I.C', 'doors', 'Right door does not open well', 'NTS'),
    ('BEDROOM D', 'JOINERY', 'B.I.C', 'hinges', 'Hinges prevent door from opening fully', 'NTS'),
]


def main():
    conn = sqlite3.connect('/var/data/inspections.db')
    cur = conn.cursor()
    now = now_iso()

    print(f"=== {'DRY RUN' if DRY_RUN else 'IMPORT'}: Unit {UNIT_NUMBER} ===")
    print(f"Inspector: {INSPECTOR_NAME} ({INSPECTOR_ID})")
    print(f"Cycle: {CYCLE_ID}")
    print(f"Raw defects: {len(DEFECTS)}")
    print()

    # --- RESOLVE TEMPLATE IDs ---
    print("--- TEMPLATE RESOLUTION ---")
    resolved = []
    failed = []
    for area, cat, parent_kw, item_kw, desc, dtype in DEFECTS:
        tid, score, info = resolve_template(cur, area, cat, parent_kw, item_kw)
        if tid and score >= 0.35:
            resolved.append((tid, desc, dtype))
            print(f"  OK [{tid}] {area}>{cat}>{info} (s={score:.2f}) -> {desc}")
        else:
            failed.append((area, cat, parent_kw, item_kw, desc))
            print(f"  FAIL {area}>{cat}>{parent_kw}>{item_kw} (s={score:.2f}) -> {desc}")

    if failed:
        print(f"\n*** {len(failed)} UNRESOLVED - ABORTING ***")
        for a, c, p, i, d in failed:
            print(f"  {a} > {c} > {p} > {i}: {d}")
        conn.close()
        return

    print(f"\nResolved: {len(resolved)} defects")

    if DRY_RUN:
        print("\n=== DRY RUN COMPLETE - no DB changes ===")
        conn.close()
        return

    # --- GET UNIT ---
    cur.execute('SELECT id FROM unit WHERE unit_number=? AND tenant_id=?', (UNIT_NUMBER, TENANT))
    row = cur.fetchone()
    if not row:
        print(f"ERROR: Unit {UNIT_NUMBER} not found"); conn.close(); return
    unit_id = row[0]
    print(f"Unit ID: {unit_id}")

    # --- CHECK/CREATE INSPECTION ---
    cur.execute('SELECT id, status FROM inspection WHERE unit_id=? AND cycle_id=?', (unit_id, CYCLE_ID))
    row = cur.fetchone()
    if row:
        insp_id, status = row
        print(f"Existing inspection: {insp_id} ({status})")
        if status not in ('not_started', 'in_progress'):
            print(f"SKIP: already {status}"); conn.close(); return
    else:
        insp_id = gen_id()
        cur.execute("""INSERT INTO inspection
            (id,tenant_id,unit_id,cycle_id,inspection_date,inspector_id,inspector_name,
             status,started_at,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,'in_progress',?,?,?)""",
            (insp_id,TENANT,unit_id,CYCLE_ID,INSPECTION_DATE,INSPECTOR_ID,INSPECTOR_NAME,now,now,now))
        print(f"Created inspection: {insp_id}")

    cur.execute("UPDATE inspection SET inspector_id=?,inspector_name=?,updated_at=? WHERE id=?",
                (INSPECTOR_ID,INSPECTOR_NAME,now,insp_id))
    cur.execute("UPDATE cycle_unit_assignment SET inspector_id=? WHERE cycle_id=? AND unit_id=?",
                (INSPECTOR_ID,CYCLE_ID,unit_id))

    # --- CREATE INSPECTION ITEMS ---
    cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=?', (insp_id,))
    if cur.fetchone()[0] > 0:
        print("Items already exist")
    else:
        cur.execute('SELECT id FROM item_template WHERE tenant_id=?', (TENANT,))
        for t in cur.fetchall():
            cur.execute("INSERT INTO inspection_item (id,tenant_id,inspection_id,item_template_id,status,marked_at) VALUES(?,?,?,?,'pending',NULL)",
                        (gen_id(),TENANT,insp_id,t[0]))
        print("Created 523 inspection items")

    # --- MARK EXCLUSIONS ---
    cur.execute("SELECT DISTINCT item_template_id FROM cycle_excluded_item WHERE cycle_id=?", (CYCLE_ID,))
    excluded_ids = set(r[0] for r in cur.fetchall())
    print(f"Exclusions: {len(excluded_ids)}")
    sk = 0
    for eid in excluded_ids:
        cur.execute("UPDATE inspection_item SET status='skipped',marked_at=? WHERE inspection_id=? AND item_template_id=?",
                    (now,insp_id,eid))
        sk += cur.rowcount
    print(f"Skipped: {sk}")

    # --- EXCLUSION OVERLAP CHECK ---
    print("\n--- EXCLUSION CHECK ---")
    clean = []
    dropped = 0
    for tid, desc, dtype in resolved:
        if tid in excluded_ids:
            print(f"  DROPPED [{tid}] {desc}")
            dropped += 1
        else:
            clean.append((tid, desc, dtype))
    print(f"Dropped: {dropped}, Clean: {len(clean)}")

    # --- WASH + INSERT DEFECTS ---
    print("\n--- DEFECTS ---")
    dc = 0
    for tid, desc, dtype in clean:
        washed, cat = wash_description(cur, tid, desc)
        did = gen_id()
        dt = 'not_installed' if dtype == 'NI' else 'not_to_standard'
        cur.execute("""INSERT INTO defect (id,tenant_id,unit_id,item_template_id,raised_cycle_id,
            defect_type,status,original_comment,created_at,updated_at)
            VALUES(?,?,?,?,?,?,'open',?,?,?)""",
            (did,TENANT,unit_id,tid,CYCLE_ID,dt,washed,now,now))
        ist = 'not_installed' if dtype == 'NI' else 'not_to_standard'
        cur.execute("UPDATE inspection_item SET status=?,comment=?,marked_at=? WHERE inspection_id=? AND item_template_id=?",
                    (ist,washed,now,insp_id,tid))
        dc += 1
        print(f"  [{tid}] {washed}")
    print(f"Defects created: {dc}")

    # --- MARK OK ---
    cur.execute("UPDATE inspection_item SET status='ok',marked_at=? WHERE inspection_id=? AND status='pending'",
                (now,insp_id))
    print(f"OK: {cur.rowcount}")

    # --- STATUS ---
    cur.execute("UPDATE inspection SET status='reviewed',submitted_at=?,updated_at=? WHERE id=?",
                (now,now,insp_id))
    cur.execute("UPDATE batch_unit SET status='reviewed' WHERE unit_id=? AND cycle_id=?",
                (unit_id,CYCLE_ID))
    cur.execute("UPDATE unit SET status='in_progress' WHERE id=? AND status='not_started'", (unit_id,))

    # --- VERIFY ---
    print("\n=== VERIFY ===")
    for s in ['skipped','ok','not_to_standard','not_installed','pending']:
        cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=? AND status=?',(insp_id,s))
        print(f"  {s}: {cur.fetchone()[0]}")
    cur.execute('SELECT COUNT(*) FROM defect WHERE unit_id=? AND raised_cycle_id=? AND status=?',
                (unit_id,CYCLE_ID,'open'))
    print(f"  defects: {cur.fetchone()[0]}")
    total = 0
    for s in ['skipped','ok','not_to_standard','not_installed','pending']:
        cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=? AND status=?',(insp_id,s))
        total += cur.fetchone()[0]
    print(f"  total items: {total} (expect 523)")

    conn.commit()
    print("\nCOMMITTED")
    conn.close()

if __name__ == '__main__':
    main()
