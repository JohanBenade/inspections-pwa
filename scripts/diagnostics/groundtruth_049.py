import sqlite3
c = sqlite3.connect('/var/data/inspections.db'); c.row_factory = sqlite3.Row
TID = 'MONOGRAPH'
UN = '049'

u = c.execute("SELECT id, floor, block FROM unit WHERE tenant_id=? AND unit_number=?", [TID, UN]).fetchone()
uid = u['id']
insp = c.execute("""SELECT id, cycle_id, cycle_number, exclusion_list_id FROM inspection
    WHERE unit_id=? AND tenant_id=? AND cycle_number=2 ORDER BY created_at DESC LIMIT 1""",
    [uid, TID]).fetchone()
print(f"Unit {UN} | uid={uid} floor={u['floor']} | C2 insp={insp['id']} cycle={insp['cycle_id']}"
      f" excl_link={insp['exclusion_list_id']}")

# --- LIVE items: pending + no prior defects, off the actual inspection_item rows ---
rows = c.execute("""SELECT status, COALESCE(has_prior_defects,0) hpd, COUNT(*) n
    FROM inspection_item WHERE inspection_id=? GROUP BY status, hpd ORDER BY status, hpd""",
    [insp['id']]).fetchall()
print("\nLIVE inspection_item status breakdown (status | hpd | count):")
live_items_cohort = 0
for r in rows:
    print(f"  {r['status']:18} hpd={r['hpd']} -> {r['n']}")
    if r['status'] == 'pending' and r['hpd'] == 0:
        live_items_cohort = r['n']
print(f"  => LIVE pending+no-prior items = {live_items_cohort}")

# --- LIVE defects: replicate _desnag_progress rule against cycle_number=2 ---
cn = insp['cycle_number']
defs = c.execute("""SELECT status, raised_cycle_number, cleared_cycle_number
    FROM defect WHERE unit_id=? AND tenant_id=?""", [uid, TID]).fetchall()
d_count = 0
for d in defs:
    if d['raised_cycle_number'] is None or d['raised_cycle_number'] >= cn:
        continue
    if d['status'] == 'open':
        d_count += 1
    elif d['status'] == 'cleared' and d['cleared_cycle_number'] == cn:
        d_count += 1
print(f"\nLIVE defects (desnag rule, cycle={cn}) = {d_count}")

# --- LIVE latents ---
lats = c.execute("""SELECT rectified_at, rectified_at_cycle_number
    FROM latent_area_note WHERE unit_id=? AND tenant_id=?""", [uid, TID]).fetchall()
l_count = sum(1 for l in lats if l['rectified_at'] is None or l['rectified_at_cycle_number'] == cn)
print(f"LIVE latents = {l_count}")

print(f"\n=== LIVE TOTAL: {d_count} def + {l_count} lat + {live_items_cohort} items = {d_count + l_count + live_items_cohort}")
print(f"=== PROJECTION said: 23 def + 0 lat + 47 items = 70")
