"""
Batch Import: 6 units from 2026-02-17 Word docs
Inspector: Thembinkosi Biko (insp-004)

Units 054, 055, 056: Block 6 Ground Round 1 -> cycle 36e85327
Unit 046: Block 6 Ground Round 1 -> cycle 36e85327 (has stale test-cycle-099 inspection)
Units 029, 030: Block 5 Ground Round 2 -> NEW cycle (created by this script)

Exclusions: 86 per unit (copied from source cycle, same as all existing units)
Total defects: 137
"""
import sqlite3
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

TENANT = 'MONOGRAPH'
INSPECTOR_ID = 'insp-004'
INSPECTOR_NAME = 'Thembinkosi Biko'
INSPECTION_DATE = '2026-02-17'

# Cycle assignments
CYCLE_B6G = '36e85327'       # Block 6 Ground Round 1 (054, 055, 056, 046)
CYCLE_B5G_R1 = '792812c7'   # Block 5 Ground Round 1 (exclusion source for 029, 030)
# CYCLE_B5G_R2 will be created by this script

EXCLUSION_SOURCES = {
    '029': '792812c7',
    '030': '792812c7',
    '046': '36e85327',
    '054': '36e85327',
    '055': '36e85327',
    '056': '36e85327',
}

# ============================================================
# DEFECT DATA PER UNIT
# (template_id, raw_description, defect_type NTS/NI)
# ============================================================

UNIT_DEFECTS = {
    '029': [
        # KITCHEN
        ('470a5289', 'Shelf not fitted into place', 'NTS'),
        ('9f743e7d', 'Finish is scratched close to stove', 'NTS'),
        # BATHROOM
        ('b6b5d166', 'Scratches on door', 'NTS'),
        ('b6b5d166', 'Pencil marks to be cleaned off', 'NTS'),
        ('b6b5d166', 'Door frame has dents and areas where paint is peeling off', 'NTS'),
        ('6f84fade', 'Screw on frame that door hits when closed to be removed', 'NTS'),
        ('7cd10dda', 'There is a lot of sand around WC waste pipe-to be cleaned', 'NTS'),
        ('1beaecc9', 'SHR Mixer has loose plate to be secured onto wall', 'NTS'),
        ('019d6605', 'SHR Rose has loose plate to be secured onto wall', 'NTS'),
        # BEDROOM A
        ('028e00cc', 'Stain/dirty mark by door', 'NTS'),
        ('ed15ccaf', 'B.I.C clothing rail not installed', 'NI'),
        ('519d4580', 'B.I.C door stop not installed', 'NI'),
        # BEDROOM B
        ('1eb374be', 'B.I.C clothing rail not installed', 'NI'),
        ('7b3e816b', 'B.I.C door stop not installed', 'NI'),
        # BEDROOM C
        ('968ba64b', 'B.I.C clothing rail not installed', 'NI'),
        # BEDROOM D
        ('212d83e1', 'Door is chipped around lockset (bottom left)', 'NTS'),
        ('4e65f3e9', 'B.I.C clothing rail not installed', 'NI'),
        ('b38587a1', 'Study desk steel frame right underneath table is bent', 'NTS'),
    ],
    '030': [
        # KITCHEN
        ('16e941da', 'Stained damped wall by D1 bottom sides', 'NTS'),
        ('522b4aeb', 'Chipped tile between bedroom a and b', 'NTS'),
        ('470a5289', 'Shelf not fitted into place', 'NTS'),
        ('25bd6002', 'Third cabinet/drawer does not close all the way and stiff to open', 'NTS'),
        # BATHROOM
        ('b6b5d166', 'Dents by door handle', 'NTS'),
        ('818a1716', 'Chipped tile by door stopper', 'NTS'),
        ('1beaecc9', 'SHR Mixer has loose plate to be secured onto wall', 'NTS'),
        ('019d6605', 'SHR Rose has loose plate to be secured onto wall', 'NTS'),
        # BEDROOM A
        ('028e00cc', 'Damp and stained wall under study desk', 'NTS'),
        ('ed15ccaf', 'B.I.C clothing rail not installed', 'NI'),
        ('519d4580', 'B.I.C door stopper not installed', 'NI'),
        # BEDROOM B
        ('31774738', 'Door makes loud clipping sound when opening/closing', 'NTS'),
        ('1eb374be', 'B.I.C clothing rail not installed', 'NI'),
        ('7b3e816b', 'B.I.C door stopper not installed', 'NI'),
        # BEDROOM C
        ('91db75ab', 'Door frame has dents and scratches by lockset/striker plate', 'NTS'),
        ('968ba64b', 'B.I.C clothing rail not installed', 'NI'),
        # BEDROOM D
        ('212d83e1', 'Door has paint stains on interior side', 'NTS'),
        ('6f905df9', 'Door hits door stop plate, not rubber-damaging door', 'NTS'),
        ('4e65f3e9', 'B.I.C clothing rail not installed', 'NI'),
    ],
    '046': [
        # KITCHEN
        ('1161cc67', 'One bulb missing', 'NTS'),
        ('406b0286', 'Board fixed to wall inside cupboard is stained and to be cleaned/finished', 'NTS'),
        # BATHROOM
        ('1658968a', 'Door stop is loose', 'NTS'),
        ('1beaecc9', 'SHR Mixer has loose plate to be secured onto wall', 'NTS'),
        ('019d6605', 'SHR Rose has loose plate to be secured onto wall', 'NTS'),
        # BEDROOM A
        ('212cf40b', 'Screws on door frame that door hits when closing to be removed', 'NTS'),
        # BEDROOM B
        ('622ed9f0', 'Screws on door frame that door hits when closing to be removed', 'NTS'),
        ('5d1dc2bd', 'There is a loose screw left hanging and bent on study desk carcass', 'NTS'),
        ('1eb374be', 'B.I.C clothing rail not installed', 'NI'),
        ('7b3e816b', 'B.I.C door stopper not installed', 'NI'),
        # BEDROOM C
        ('91db75ab', 'Screws on door frame that door hits when closing to be removed', 'NTS'),
        # BEDROOM D
        ('44757b47', 'Wall right above W3 is damaged due to construction right outside unit, supervisor notified-will be fixed', 'NTS'),
    ],
    '054': [
        # KITCHEN
        ('16e941da', 'Broom cupboard bottom wall by D1 not painted', 'NTS'),
        ('16e941da', 'Stains on wall above broom cupboard, one more coat to get rid of stains', 'NTS'),
        ('1161cc67', 'One bulb missing', 'NTS'),
        ('7af717d1', 'Fixing to wall not done legibly, to be fixed', 'NTS'),
        ('406b0286', 'Board fixed to wall inside broom cupboard is badly cracked', 'NTS'),
        ('522b4aeb', 'Chipped tile as indicated', 'NTS'),
        ('6957702f', 'Grout dove grey is missing in between tiles as indicated', 'NTS'),
        # BATHROOM
        ('124015dc', 'Door touches the floor when swinging to open or close', 'NTS'),
        ('39fe1eda', 'WC indicator bolt and thumb turn don\'t turn at all', 'NTS'),
        ('8d063b43', 'D3 magnetic door doesn\'t close at all', 'NTS'),
        ('019d6605', 'SHR Rose plate is loose, to be secured onto wall', 'NTS'),
        ('1beaecc9', 'SHR Mixer plate is loose, to be secured to wall', 'NTS'),
        # BEDROOM A
        ('196912e5', 'Signage is not installed', 'NI'),
        ('519d4580', 'B.I.C door stop not installed', 'NI'),
        ('ed15ccaf', 'Clothing hanger not installed inside of B.I.C.', 'NI'),
        # BEDROOM B
        ('a829adca', 'Signage is not installed', 'NI'),
        ('81520953', 'Grout dove grey is missing in between tiles as indicated', 'NTS'),
        ('7b3e816b', 'B.I.C door stop not installed', 'NI'),
        ('1eb374be', 'Clothing hanger not installed inside of B.I.C.', 'NI'),
        # BEDROOM C
        ('dad5b52a', 'Signage is not installed', 'NI'),
        ('85620ac4', 'Chipped tile as indicated', 'NTS'),
        ('f34b4fe9', 'There is an area on floor where grout dove grey is missing between tiles', 'NTS'),
        ('968ba64b', 'Clothing hanger not installed inside of B.I.C.', 'NI'),
        # BEDROOM D
        ('6f905df9', 'Door doesn\'t touch the rubber of door stop, hits door stop plate', 'NTS'),
        ('04d2ad00', 'Signage is not installed', 'NI'),
        ('956b6837', 'Grout dove grey is missing in between tiles as indicated', 'NTS'),
        ('135828f3', 'Orchid bay paint on left side of study desk', 'NTS'),
        ('4e65f3e9', 'Clothing hanger not installed inside of B.I.C.', 'NI'),
    ],
    '055': [
        # KITCHEN
        ('522b4aeb', 'Cracked tile', 'NTS'),
        ('3cf49a3d', 'Tile skirting not legibly done underside cupboard', 'NTS'),
        ('7889a386', 'Tile trim at W1a missing besides tile', 'NTS'),
        # BATHROOM
        ('6f84fade', 'Dents on frame finish', 'NTS'),
        ('b9805e6c', 'WC shut off valve doesn\'t work/turn to open or close', 'NTS'),
        ('1beaecc9', 'SHR Mixer plate is loose', 'NTS'),
        ('019d6605', 'SHR Rose plate is loose', 'NTS'),
        ('b5e33d23', 'Shut off valve cold is stiff, hard to turn', 'NTS'),
        ('3fbc1db8', 'Shut off valve hot is stiff, hard to turn', 'NTS'),
        # BEDROOM A
        ('557dfea3', 'Residence lock handle has paint stain and does not kick back up', 'NTS'),
        ('039bdc70', 'Door hits door stopper plate and not rubber', 'NTS'),
        ('14eb7511', 'Tile skirting underside B.I.C not legibly done', 'NTS'),
        ('ed15ccaf', 'Missing clothing rail inside B.I.C', 'NI'),
        ('519d4580', 'B.I.C door stopper not installed', 'NI'),
        # BEDROOM B
        ('622ed9f0', 'Frame finish has dents', 'NTS'),
        ('aef89fec', 'Door hits door stopper plate not rubber', 'NTS'),
        ('1136f030', 'Tile skirting underside B.I.C not legibly done', 'NTS'),
        ('2ed16ab7', 'Chipped tile', 'NTS'),
        ('1eb374be', 'Clothing rail inside B.I.C not installed', 'NI'),
        ('7b3e816b', 'B.I.C door stopper not installed', 'NI'),
        ('43f70971', 'Floating shelf has paint stains', 'NTS'),
        # BEDROOM C
        ('9fdcd89e', 'Dents on door edges', 'NTS'),
        ('80177e8e', 'Inconsistent, uneven paint all over door exterior', 'NTS'),
        ('91db75ab', 'Frame needs one more paint coat as its uneven', 'NTS'),
        ('ed6e3126', 'Door hits door stopper plate not rubber', 'NTS'),
        ('968ba64b', 'Clothing rail inside B.I.C is missing', 'NI'),
        ('85620ac4', 'Chipped tile', 'NTS'),
        ('6a0771ae', 'B.I.C underside tile skirting not finished legibly', 'NTS'),
        # BEDROOM D
        ('6e2d53af', 'Dents and peeling off on frame', 'NTS'),
        ('6f905df9', 'Door hits door stop plate not rubber', 'NTS'),
        ('a39a8899', 'B.I.C underside tile skirting not finished legibly', 'NTS'),
        ('a39a8899', 'One tile skirting missing where B.I.C starts (left side)', 'NTS'),
        ('4e65f3e9', 'Clothing rail inside B.I.C not installed', 'NI'),
    ],
    '056': [
        # KITCHEN
        ('2cd5bdf0', 'W1a X1 burglar bar doesn\'t have a black cap', 'NTS'),
        ('3cf49a3d', 'Tile skirting not legibly done underside cupboard', 'NTS'),
        ('7af717d1', 'Fixing to wall not legibly done, to be fixed', 'NTS'),
        ('255488c3', 'Loose hinge', 'NTS'),
        # LOUNGE
        ('3cb1b144', 'Chipped tile as indicated', 'NTS'),
        # BATHROOM
        ('1658968a', 'Door stop is loose', 'NTS'),
        ('1beaecc9', 'SHR Mixer plate is loose', 'NTS'),
        ('019d6605', 'SHR Rose plate is loose', 'NTS'),
        # BEDROOM A
        ('afcc1bc2', 'Dents and cracks on door', 'NTS'),
        ('039bdc70', 'Door is hitting door stopper plate not rubber', 'NTS'),
        ('14eb7511', 'Tile skirting underside B.I.C not legibly done', 'NTS'),
        ('ed15ccaf', 'Missing clothing rail inside B.I.C', 'NI'),
        ('519d4580', 'B.I.C door stopper not installed', 'NI'),
        ('fa7f85d7', 'Floating shelf has crack by Window', 'NTS'),
        # BEDROOM B
        ('340d94a3', 'Door finish has dents', 'NTS'),
        ('1136f030', 'Tile skirting underside B.I.C not legibly done', 'NTS'),
        ('1eb374be', 'Clothing rail inside B.I.C not installed', 'NI'),
        ('7b3e816b', 'B.I.C door stopper not installed', 'NI'),
        # BEDROOM C
        ('968ba64b', 'Clothing rail inside B.I.C is not installed', 'NI'),
        ('f42cffed', 'Study desk has loose screw hanging', 'NTS'),
        # BEDROOM D
        ('6e2d53af', 'Dents on frame', 'NTS'),
        ('6f905df9', 'Door hits door stop plate not rubber', 'NTS'),
        ('44757b47', 'Dents behind door', 'NTS'),
        ('a39a8899', 'Grout missing by skirting', 'NTS'),
        ('a39a8899', 'Tile skirting not legibly finished to B.I.C underside', 'NTS'),
        ('07ad730b', 'B.I.C has paint stains', 'NTS'),
        ('4e65f3e9', 'Clothing rail inside B.I.C not installed', 'NI'),
    ],
}

# ============================================================
# HELPERS
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
        SELECT ct.category_name FROM item_template it
        JOIN category_template ct ON it.category_id = ct.id WHERE it.id = ?
    """, (item_template_id,))
    cat_row = cur.fetchone()
    cat_name = cat_row[0] if cat_row else 'UNKNOWN'

    cur.execute("""
        SELECT description FROM defect_library
        WHERE tenant_id = ? AND item_template_id = ? ORDER BY usage_count DESC
    """, (TENANT, item_template_id))
    item_entries = [r[0] for r in cur.fetchall()]
    if item_entries:
        match, score = fuzzy_match(raw_desc, item_entries)
        if match:
            return match, f"item-specific ({score:.2f})", cat_name

    cur.execute("""
        SELECT description FROM defect_library
        WHERE tenant_id = ? AND category_name = ? AND item_template_id IS NULL
        ORDER BY usage_count DESC
    """, (TENANT, cat_name))
    cat_entries = [r[0] for r in cur.fetchall()]
    if cat_entries:
        match, score = fuzzy_match(raw_desc, cat_entries)
        if match:
            return match, f"category-fallback ({score:.2f})", cat_name

    cleaned = raw_desc.strip()
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned, "NEW", cat_name

# ============================================================
# MAIN
# ============================================================
def main():
    conn = sqlite3.connect('/var/data/inspections.db')
    cur = conn.cursor()
    now = now_iso()

    print("=" * 70)
    print("BATCH IMPORT: 2026-02-17 (6 units, 137 defects)")
    print("=" * 70)

    # --- STEP 0: Verify all template IDs exist ---
    print("\n--- VERIFYING ALL TEMPLATE IDs ---")
    all_ids = set()
    for unit_num, defects in UNIT_DEFECTS.items():
        for tid, _, _ in defects:
            all_ids.add(tid)
    all_valid = True
    for tid in sorted(all_ids):
        cur.execute('SELECT id FROM item_template WHERE id=? AND tenant_id=?', (tid, TENANT))
        if not cur.fetchone():
            print(f"  MISSING: {tid}")
            all_valid = False
    if not all_valid:
        print("ABORTING - fix template IDs")
        conn.close()
        return
    print(f"  All {len(all_ids)} unique template IDs verified")

    # --- STEP 1: Block 5 Ground Round 2 cycle (pre-created) ---
    cycle_b5g_r2 = '855cd617'
    print(f"\n--- B5G ROUND 2 CYCLE: {cycle_b5g_r2} ---")

    # Map units to cycles
    UNIT_CYCLES = {
        '029': cycle_b5g_r2,
        '030': cycle_b5g_r2,
        '046': CYCLE_B6G,
        '054': CYCLE_B6G,
        '055': CYCLE_B6G,
        '056': CYCLE_B6G,
    }

    # --- STEP 2: Process each unit ---
    total_defects = 0
    total_new_library = 0

    for unit_num in ['054', '055', '056', '046', '029', '030']:
        defects = UNIT_DEFECTS[unit_num]
        cycle_id = UNIT_CYCLES[unit_num]
        exc_source = EXCLUSION_SOURCES[unit_num]

        print(f"\n{'='*60}")
        print(f"UNIT {unit_num} | Cycle: {cycle_id} | Defects: {len(defects)}")
        print(f"{'='*60}")

        # Get unit
        cur.execute('SELECT id FROM unit WHERE unit_number=? AND tenant_id=?', (unit_num, TENANT))
        row = cur.fetchone()
        if not row:
            print(f"  ERROR: Unit {unit_num} not found - SKIPPING")
            continue
        unit_id = row[0]

        # Check for existing inspection on this cycle
        cur.execute('SELECT id, status FROM inspection WHERE unit_id=? AND cycle_id=?', (unit_id, cycle_id))
        row = cur.fetchone()
        if row:
            insp_id, insp_status = row
            print(f"  Existing inspection: {insp_id} (status={insp_status})")
            if insp_status not in ('not_started', 'in_progress'):
                print(f"  WARNING: Already at {insp_status} - SKIPPING")
                continue
        else:
            insp_id = gen_id()
            cur.execute("""
                INSERT INTO inspection
                (id, tenant_id, unit_id, cycle_id, inspection_date,
                 inspector_id, inspector_name, status, started_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'in_progress', ?, ?, ?)
            """, (insp_id, TENANT, unit_id, cycle_id, INSPECTION_DATE,
                  INSPECTOR_ID, INSPECTOR_NAME, now, now, now))
            print(f"  Created inspection: {insp_id}")

        # Update inspector
        cur.execute("UPDATE inspection SET inspector_id=?, inspector_name=?, updated_at=? WHERE id=?",
                    (INSPECTOR_ID, INSPECTOR_NAME, now, insp_id))

        # Create 523 inspection items (if not already present)
        cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=?', (insp_id,))
        existing_items = cur.fetchone()[0]
        if existing_items > 0:
            print(f"  Items already exist: {existing_items}")
        else:
            cur.execute('SELECT id FROM item_template WHERE tenant_id=?', (TENANT,))
            templates = cur.fetchall()
            for t in templates:
                cur.execute("""
                    INSERT INTO inspection_item
                    (id, tenant_id, inspection_id, item_template_id, status, marked_at)
                    VALUES (?, ?, ?, ?, 'pending', NULL)
                """, (gen_id(), TENANT, insp_id, t[0]))
            print(f"  Created {len(templates)} inspection items")

        # Mark exclusions
        cur.execute("""
            SELECT DISTINCT ii.item_template_id
            FROM inspection_item ii JOIN inspection i ON ii.inspection_id = i.id
            WHERE i.cycle_id = ? AND ii.status = 'skipped'
        """, (exc_source,))
        excluded_ids = set(r[0] for r in cur.fetchall())
        skipped = 0
        for eid in excluded_ids:
            cur.execute("UPDATE inspection_item SET status='skipped', marked_at=? WHERE inspection_id=? AND item_template_id=?",
                        (now, insp_id, eid))
            skipped += cur.rowcount
        print(f"  Exclusions: {len(excluded_ids)} templates, {skipped} items marked skipped")

        # Check exclusion overlaps and create defects
        new_library = []
        defect_count = 0
        for tid, raw_desc, dtype in defects:
            if tid in excluded_ids:
                print(f"  DROPPED (excluded): [{tid}] {raw_desc}")
                continue

            washed, source, cat = wash_description(cur, tid, raw_desc)
            if "NEW" in source:
                new_library.append((tid, cat, washed))

            defect_id = gen_id()
            defect_type = 'not_installed' if dtype == 'NI' else 'not_to_standard'
            cur.execute("""
                INSERT INTO defect
                (id, tenant_id, unit_id, item_template_id, raised_cycle_id,
                 defect_type, status, original_comment, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, ?)
            """, (defect_id, TENANT, unit_id, tid, cycle_id, defect_type, washed, now, now))

            item_status = 'not_installed' if dtype == 'NI' else 'not_to_standard'
            cur.execute("UPDATE inspection_item SET status=?, comment=?, marked_at=? WHERE inspection_id=? AND item_template_id=?",
                        (item_status, washed, now, insp_id, tid))
            defect_count += 1

        print(f"  Defects created: {defect_count}")
        total_defects += defect_count

        # Mark remaining as OK
        cur.execute("UPDATE inspection_item SET status='ok', marked_at=? WHERE inspection_id=? AND status='pending'",
                    (now, insp_id))
        print(f"  Marked OK: {cur.rowcount}")

        # Add new library entries
        if new_library:
            for tid, cat, desc in new_library:
                cur.execute("""
                    INSERT INTO defect_library
                    (id, tenant_id, category_name, item_template_id, description, usage_count, is_system, created_at)
                    VALUES (?, ?, ?, ?, ?, 1, 0, ?)
                """, (gen_id(), TENANT, cat, tid, desc, now))
            print(f"  New library entries: {len(new_library)}")
            total_new_library += len(new_library)

        # Set inspection status
        cur.execute("UPDATE inspection SET status='submitted', submitted_at=?, updated_at=? WHERE id=?",
                    (now, now, insp_id))

        # Update unit status
        cur.execute("UPDATE unit SET status='in_progress' WHERE id=? AND status='not_started'", (unit_id,))

        # Verify
        print(f"\n  VERIFICATION:")
        for s in ['skipped', 'ok', 'not_to_standard', 'not_installed', 'pending']:
            cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=? AND status=?', (insp_id, s))
            print(f"    {s}: {cur.fetchone()[0]}")
        cur.execute('SELECT COUNT(*) FROM defect WHERE unit_id=? AND raised_cycle_id=? AND status=?',
                    (unit_id, cycle_id, 'open'))
        print(f"    defects (this cycle): {cur.fetchone()[0]}")
        cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=?', (insp_id,))
        print(f"    total items: {cur.fetchone()[0]} (expected 523)")

    # --- FINAL SUMMARY ---
    print(f"\n{'='*70}")
    print("FINAL SUMMARY")
    print(f"{'='*70}")
    print(f"  Total defects created: {total_defects}")
    print(f"  New library entries: {total_new_library}")
    print(f"  B5G Round 2 cycle: {cycle_b5g_r2}")

    cur.execute('SELECT COUNT(*) FROM defect WHERE status="open" AND tenant_id=?', (TENANT,))
    print(f"  Total open defects (all): {cur.fetchone()[0]}")

    for cid, label in [(CYCLE_B6G, 'B6G'), (cycle_b5g_r2, 'B5G-R2'), (CYCLE_B5G_R1, 'B5G-R1'), ('179b2b9d', 'B5-1F')]:
        cur.execute('SELECT COUNT(*) FROM defect WHERE status="open" AND raised_cycle_id=?', (cid,))
        d = cur.fetchone()[0]
        cur.execute('SELECT COUNT(DISTINCT i.unit_id) FROM inspection i WHERE i.cycle_id=? AND i.tenant_id=?', (cid, TENANT))
        u = cur.fetchone()[0]
        print(f"  {label} ({cid}): {d} defects, {u} units")

    conn.commit()
    print("\nCOMMITTED SUCCESSFULLY")
    conn.close()

if __name__ == '__main__':
    main()
