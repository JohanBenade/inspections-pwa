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

UNIT_NUMBER = '151'
INSPECTOR_ID = 'insp-005'
INSPECTOR_NAME = 'Lindokuhle Zulu'
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
# Hardcoded overrides for items the fuzzy resolver cannot find
# (area, category, parent_kw, item_kw) -> template_id
TEMPLATE_OVERRIDES = {
    # Kitchen root items
    ('KITCHEN', 'WALLS', 'paint'): '16e941da',
    ('KITCHEN', 'ELECTRICAL', 'DB'): '7414ad92',
    ('KITCHEN', 'FLOOR', 'Soft joint'): 'bdafda18',
    ('KITCHEN', 'CEILING', 'plaster recess'): '6eb3af36',
    # Lounge items
    ('LOUNGE', 'WALLS', 'Wall', 'paint'): 'c248c406',
    ('LOUNGE', 'FLOOR', 'Floor', 'chipped'): '3cb1b144',
    ('LOUNGE', 'FLOOR', 'Floor', 'grout'): 'feafbe9d',
    ('LOUNGE', 'FLOOR', 'Floor', 'skirting'): 'a46f716d',
    ('LOUNGE', 'CEILING', 'plaster recess'): 'a4163cb8',
    ('LOUNGE', 'ELECTRICAL', 'Double plug'): 'fa47bce5',
    # Bedroom floors (verified)
    ('BEDROOM A', 'FLOOR', 'Floor', 'chipped'): '41c9bd11',
    ('BEDROOM A', 'FLOOR', 'Floor', 'grout'): 'e1d9e932',
    ('BEDROOM A', 'FLOOR', 'Floor', 'skirting'): '14eb7511',
    ('BEDROOM B', 'FLOOR', 'Floor', 'chipped'): '2ed16ab7',
    ('BEDROOM B', 'FLOOR', 'Floor', 'grout'): '81520953',
    ('BEDROOM B', 'FLOOR', 'Floor', 'skirting'): '1136f030',
    ('BEDROOM C', 'FLOOR', 'Floor', 'chipped'): '85620ac4',
    ('BEDROOM C', 'FLOOR', 'Floor', 'grout'): 'f34b4fe9',
    ('BEDROOM C', 'FLOOR', 'Floor', 'skirting'): '6a0771ae',
    ('BEDROOM D', 'FLOOR', 'Floor', 'chipped'): '54ac6a45',
    ('BEDROOM D', 'FLOOR', 'Floor', 'grout'): '956b6837',
    ('BEDROOM D', 'FLOOR', 'Floor', 'skirting'): 'a39a8899',
    # Bedroom walls override
    ('BEDROOM C', 'WALLS', 'Wall', 'finish'): '5628303a',
    # Bedroom study desk light
    ('BEDROOM B', 'ELECTRICAL', 'study desk light'): 'e2fd6318',
    # Floating shelves (verified)
    ('BEDROOM A', 'JOINERY', 'Floating shelf', 'finish'): '468ece9d',
    ('BEDROOM B', 'JOINERY', 'Floating shelf', 'finish'): '262bfbeb',
    ('BEDROOM C', 'JOINERY', 'Floating shelf', 'finish'): '2f006892',
    ('BEDROOM D', 'JOINERY', 'Floating shelf', 'finish'): '135828f3',
    ('BEDROOM A', 'JOINERY', 'Floating shelf', 'installed'): '519d4580',
    ('BEDROOM B', 'JOINERY', 'Floating shelf', 'installed'): '7b3e816b',
    ('BEDROOM C', 'JOINERY', 'Floating shelf', 'installed'): '0b929eb3',
    ('BEDROOM D', 'JOINERY', 'Floating shelf', 'installed'): 'f653cf83',
    # Bathroom floor/ceiling/plumbing (verified)
    ('BATHROOM', 'FLOOR', 'Floor', 'chipped'): '818a1716',
    ('BATHROOM', 'FLOOR', 'Floor', 'grout'): '8fa8781c',
    ('BATHROOM', 'CEILING', 'Ceiling', 'paint'): 'faea42ac',
    ('BATHROOM', 'PLUMBING', 'WC', 'installation'): '8667f32c',
    ('BATHROOM', 'PLUMBING', 'WC', 'shut off'): 'b9805e6c',
    ('BATHROOM', 'PLUMBING', 'Shut off Cold'): 'a9e99c5e',
    ('BATHROOM', 'PLUMBING', 'Shut off Hot'): 'e5372c9d',
    ('BATHROOM', 'PLUMBING', 'Arm'): '019d6605',
}

DEFECTS = [
    # KITCHEN (door/frame/ironmongery DROPPED - kitchen front door exclusion)
    ('KITCHEN', 'WALLS', 'paint', 'orchid bay', 'Paint is chipped and has dirt marks as indicated', 'NTS'),
    ('KITCHEN', 'WALLS', 'Splash back at sink', 'tile trim', 'Gap between tile trim and tile at window 1a as indicated', 'NTS'),
    ('KITCHEN', 'WALLS', 'Splash back at sink', 'tile into window', 'There is a dirt mark in the window sill as indicated', 'NTS'),
    ('KITCHEN', 'WALLS', 'Splash back at sink', 'wrap', 'Splash back wrap at sink is peeling as indicated', 'NTS'),
    ('KITCHEN', 'WALLS', 'Splash back at sink', 'grout', 'Gap in the grout as indicated', 'NTS'),
    ('KITCHEN', 'WALLS', 'Stove splash back', 'tile trim', 'Gap between tile trim and the tile', 'NTS'),
    ('KITCHEN', 'WALLS', 'Stove splash back', 'grout', 'Gap in grout as indicated', 'NTS'),
    ('KITCHEN', 'WINDOWS', 'W1', 'hinges', 'Hinges are beginning to rust', 'NTS'),
    ('KITCHEN', 'WINDOWS', 'W1a', 'frame', 'Frame has paint marks as indicated', 'NTS'),
    ('KITCHEN', 'WINDOWS', 'W1a', 'glass', 'Glass is broken as indicated', 'NTS'),
    ('KITCHEN', 'WINDOWS', 'W1a', 'hinges', 'Hinges are making a sound and make window difficult to close', 'NTS'),
    ('KITCHEN', 'WINDOWS', 'W1a', 'hinges', 'The window is hard to close', 'NTS'),
    ('KITCHEN', 'FLOOR', 'Soft joint', 'finish', 'Soft joint application is not consistent as indicated', 'NTS'),
    ('KITCHEN', 'FLOOR', 'Floor', 'grout', 'Gap in grout as indicated', 'NTS'),
    ('KITCHEN', 'FLOOR', 'Floor', 'tile skirting', 'Gap between tile skirting and the floor', 'NTS'),
    ('KITCHEN', 'FLOOR', 'Floor', 'tile skirting', 'Gap between tile skirting and stove lockable', 'NTS'),
    ('KITCHEN', 'ELECTRICAL', 'DB', 'DB', 'DB is not flushed to wall and has paint marks', 'NTS'),
    ('KITCHEN', 'ELECTRICAL', 'Stove', 'operation', 'Stove needs to be cleaned', 'NTS'),
    ('KITCHEN', 'JOINERY', 'Sink pack', 'carcass', 'Carcass is chipped and not to standard as indicated', 'NTS'),
    ('KITCHEN', 'JOINERY', 'Sink pack', 'finish', 'Top is not smooth as indicated', 'NTS'),
    ('KITCHEN', 'JOINERY', 'Bin drawer', 'runner', 'There is sand in the runners', 'NTS'),
    ('KITCHEN', 'JOINERY', 'Drawer pack', 'finish', 'Top is not smooth as indicated', 'NTS'),
    ('KITCHEN', 'JOINERY', 'Lockable pack 3&4', 'fixing', 'Fixing to wall is not to standard', 'NTS'),
    ('KITCHEN', 'JOINERY', 'Lockable pack 3&4', 'carcass', 'Carcass is not to standard', 'NTS'),
    ('KITCHEN', 'JOINERY', 'Lockable pack 3&4', 'hinges', 'Hinges are missing screws as indicated', 'NTS'),
    ('KITCHEN', 'JOINERY', 'Counter seating', 'fixing', 'Fixing to wall is not to standard', 'NTS'),
    ('KITCHEN', 'JOINERY', 'Counter seating', 'leg support', 'Leg support is not stable', 'NTS'),
    ('KITCHEN', 'JOINERY', 'Lockable pack 1&2', 'shelf', 'Shelves are not straight', 'NTS'),
    ('KITCHEN', 'JOINERY', 'Eye level', 'carcass', 'Carcass is scratched as indicated', 'NTS'),
    ('KITCHEN', 'JOINERY', 'Eye level', 'finish', 'Finish has paint mark as indicated', 'NTS'),
    # LOUNGE
    ('LOUNGE', 'FLOOR', 'Floor', 'chipped', 'Chipped tile as indicated', 'NTS'),
    ('LOUNGE', 'FLOOR', 'Floor', 'skirting', 'Gap between tile skirting and the floor', 'NTS'),
    ('LOUNGE', 'CEILING', 'plaster recess', 'crack', 'Crack in plaster recess', 'NTS'),
    ('LOUNGE', 'ELECTRICAL', 'Ceiling light', 'bulb', 'There is only one light bulb', 'NTS'),
    # BEDROOM A
    ('BEDROOM A', 'DOORS', 'D3', 'finished all round', 'Paint on outside is chipped as indicated', 'NTS'),
    ('BEDROOM A', 'DOORS', 'Frame', 'finish', 'Finish has overlapping paint and is scratched', 'NTS'),
    ('BEDROOM A', 'DOORS', 'Frame', 'finish', 'Screws in frame need to be removed', 'NTS'),
    ('BEDROOM A', 'DOORS', 'Frame', 'finish', 'Paint on outside is chipped as indicated', 'NTS'),
    ('BEDROOM A', 'WALLS', 'Wall', 'orchid bay', 'Paint orchid bay has dirty marks', 'NTS'),
    ('BEDROOM A', 'FLOOR', 'Floor', 'skirting', 'Gap between tile skirting and the floor', 'NTS'),
    ('BEDROOM A', 'ELECTRICAL', 'Double light switch', 'wall 02', 'Double light switch on wall 02 has paint marks', 'NTS'),
    ('BEDROOM A', 'JOINERY', 'B.I.C', 'carcass', 'Inconsistent painting in carcass back wall', 'NTS'),
    ('BEDROOM A', 'JOINERY', 'Study desk', 'screws', 'There is a missing screw', 'NTS'),
    ('BEDROOM A', 'JOINERY', 'Study desk', 'carcass', 'Remove plastic in carcass', 'NTS'),
    # BEDROOM B
    ('BEDROOM B', 'DOORS', 'D3', 'finished all round', 'Door finish has paint marks at the top of the door', 'NTS'),
    ('BEDROOM B', 'DOORS', 'D3', 'finished all round', 'Paint on outside is chipped as indicated', 'NTS'),
    ('BEDROOM B', 'DOORS', 'Frame', 'finish', 'Screws on the frame needs to be removed', 'NTS'),
    ('BEDROOM B', 'DOORS', 'Frame', 'finish', 'Paint on outside is chipped as indicated', 'NTS'),
    ('BEDROOM B', 'WALLS', 'Wall', 'orchid bay', 'Paint orchid bay is chipped and scratched as indicated', 'NTS'),
    ('BEDROOM B', 'WALLS', 'Wall', 'orchid bay', 'Paint has marks as indicated', 'NTS'),
    ('BEDROOM B', 'WINDOWS', 'W3', 'hinges', 'Hinges have rust', 'NTS'),
    ('BEDROOM B', 'FLOOR', 'Floor', 'chipped', 'Chipped tiles as indicated', 'NTS'),
    ('BEDROOM B', 'FLOOR', 'Floor', 'skirting', 'Gap between tile skirting and the floor', 'NTS'),
    ('BEDROOM B', 'JOINERY', 'Study desk', 'screws', 'Has a loose screw', 'NTS'),
    # BEDROOM C
    ('BEDROOM C', 'DOORS', 'D3', 'finished all round', 'The painting is inconsistent as indicated', 'NTS'),
    ('BEDROOM C', 'DOORS', 'Frame', 'finish', 'Finish is chipped as indicated', 'NTS'),
    ('BEDROOM C', 'DOORS', 'Frame', 'finish', 'Paint on outside needs to be cleaned', 'NTS'),
    ('BEDROOM C', 'WALLS', 'Wall', 'finish', 'Paint has dirt marks', 'NTS'),
    ('BEDROOM C', 'WALLS', 'Wall', 'finish', 'Inconsistent paint application as indicated', 'NTS'),
    ('BEDROOM C', 'WINDOWS', 'W3', 'frame', 'Frame needs to be cleaned', 'NTS'),
    ('BEDROOM C', 'WINDOWS', 'W3', 'glass', 'Glass needs to be cleaned', 'NTS'),
    ('BEDROOM C', 'WINDOWS', 'W3', 'hinges', 'Hinges have sand', 'NTS'),
    ('BEDROOM C', 'FLOOR', 'Floor', 'chipped', 'Chipped tile as indicated', 'NTS'),
    ('BEDROOM C', 'FLOOR', 'Floor', 'grout', 'Grout has paint as indicated', 'NTS'),
    ('BEDROOM C', 'ELECTRICAL', 'Double light switch', 'wall 24', 'Double light switch on wall 24 is not flushed to wall', 'NTS'),
    ('BEDROOM C', 'JOINERY', 'Floating shelf', 'finish', 'Not flushed to B.I.C', 'NTS'),
    ('BEDROOM C', 'JOINERY', 'Study desk', 'screws', 'Screw is not all the way in', 'NTS'),
    # BEDROOM D
    ('BEDROOM D', 'DOORS', 'D3', 'finished all round', 'Paint on outside is chipped as indicated', 'NTS'),
    ('BEDROOM D', 'DOORS', 'Frame', 'finish', 'Screws need to be removed', 'NTS'),
    ('BEDROOM D', 'DOORS', 'Frame', 'finish', 'There is overlapping paint as indicated', 'NTS'),
    ('BEDROOM D', 'DOORS', 'Frame', 'finish', 'Paint on outside is chipped as indicated', 'NTS'),
    ('BEDROOM D', 'WALLS', 'Wall', 'orchid bay', 'Paint is scratched as indicated', 'NTS'),
    ('BEDROOM D', 'WINDOWS', 'W4', 'hinges', 'Hinges are beginning to rust as indicated', 'NTS'),
    ('BEDROOM D', 'FLOOR', 'Floor', 'chipped', 'Chipped tiles as indicated', 'NTS'),
    ('BEDROOM D', 'FLOOR', 'Floor', 'skirting', 'Gap between tile skirting and the floor as indicated', 'NTS'),
    ('BEDROOM D', 'ELECTRICAL', 'Study desk light', 'screws', 'Study desk light screw is not all the way in', 'NTS'),
    ('BEDROOM D', 'ELECTRICAL', 'Combination plug', 'wall 19', 'Combination plug wall 19 has paint marks', 'NTS'),
    ('BEDROOM D', 'JOINERY', 'Floating shelf', 'finish', 'Not flushed to B.I.C', 'NTS'),
    ('BEDROOM D', 'JOINERY', 'Study desk', 'screws', 'Screw is not all the way in as indicated', 'NTS'),
    # BATHROOM
    ('BATHROOM', 'DOORS', 'D2', 'finished all round', 'Door rubs the frame when closing', 'NTS'),
    ('BATHROOM', 'DOORS', 'D2', 'finished all round', 'Finish has paint marks as indicated', 'NTS'),
    ('BATHROOM', 'DOORS', 'Frame', 'finish', 'Finish is chipped as indicated', 'NTS'),
    ('BATHROOM', 'DOORS', 'Frame', 'finish', 'Screws on the frame need to be removed', 'NTS'),
    ('BATHROOM', 'DOORS', 'Ironmongery', 'lockset', 'WC indicator bolt and thumb turn is not working', 'NTS'),
    ('BATHROOM', 'WALLS', 'Wall tile', 'grout', 'Grout is missing as indicated', 'NTS'),
    ('BATHROOM', 'WALLS', 'Wall tile', 'finish', 'Chipped tiles as indicated', 'NTS'),
    ('BATHROOM', 'WINDOWS', 'W5', 'frame', 'Frame is not straight', 'NTS'),
    ('BATHROOM', 'WINDOWS', 'W5', 'glass', 'Glass needs to be cleaned', 'NTS'),
    ('BATHROOM', 'FLOOR', 'Floor', 'chipped', 'Chipped tile as indicated', 'NTS'),
    ('BATHROOM', 'CEILING', 'Ceiling', 'paint', 'Has dirt spots above window', 'NTS'),
    ('BATHROOM', 'ELECTRICAL', 'Ceiling light', 'bulb', 'Only one light bulb', 'NTS'),
    ('BATHROOM', 'PLUMBING', 'WC', 'installation', 'Not flushed to wall', 'NTS'),
    ('BATHROOM', 'PLUMBING', 'WC', 'shut off', 'Shut off valve plate is loose', 'NTS'),
    ('BATHROOM', 'PLUMBING', 'Mixer', 'installation', 'Shower mixer plate is loose', 'NTS'),
    ('BATHROOM', 'PLUMBING', 'Arm', 'installation', 'Arm is loose', 'NTS'),
    ('BATHROOM', 'PLUMBING', 'Shut off Cold', 'installation', 'Plate is loose', 'NTS'),
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
        # Check overrides first (3-key and 4-key)
        override = TEMPLATE_OVERRIDES.get((area, cat, parent_kw, item_kw))
        if not override:
            override = TEMPLATE_OVERRIDES.get((area, cat, parent_kw))
        if override:
            resolved.append((override, desc, dtype))
            print(f"  OVERRIDE [{override}] {area}>{cat}>{parent_kw}>{item_kw} -> {desc}")
            continue
        # Fuzzy resolve
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
