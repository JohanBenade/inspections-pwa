import sqlite3
c = sqlite3.connect('/var/data/inspections.db'); c.row_factory = sqlite3.Row
TID = 'MONOGRAPH'
UNITS = ["014","015","016","227","248","252","269"]

tot_legit = tot_orphan = tot_clearedmismatch = 0
for un in UNITS:
    u = c.execute("SELECT id FROM unit WHERE tenant_id=? AND unit_number=?", [TID, un]).fetchone()
    insp = c.execute("""SELECT id, cycle_id FROM inspection WHERE unit_id=? AND tenant_id=? AND cycle_number=2
        ORDER BY created_at DESC LIMIT 1""", [u['id'], TID]).fetchone()
    nts = c.execute("""SELECT ii.id, ii.item_template_id, it.item_description
        FROM inspection_item ii JOIN item_template it ON it.id=ii.item_template_id
        WHERE ii.inspection_id=? AND ii.status='not_to_standard'""", [insp['id']]).fetchall()
    print(f"\n=== Unit {un}: {len(nts)} NTS items (C2 insp {insp['id']}) ===")
    for n in nts:
        defs = c.execute("""SELECT id, status, raised_cycle_number, cleared_cycle_number
            FROM defect WHERE unit_id=? AND item_template_id=? AND tenant_id=?""",
            [u['id'], n['item_template_id'], TID]).fetchall()
        if not defs:
            tot_orphan += 1
            print(f"  ORPHAN  {n['item_description'][:40]:40} | NTS but NO defect row")
        else:
            statuses = [f"{d['status']}(r{d['raised_cycle_number']}/c{d['cleared_cycle_number']})" for d in defs]
            has_open = any(d['status']=='open' for d in defs)
            if has_open:
                tot_legit += 1
                tag = "LEGIT  "
            else:
                tot_clearedmismatch += 1
                tag = "MISMATCH"
            print(f"  {tag} {n['item_description'][:40]:40} | defects: {', '.join(statuses)}")

print(f"\n=== SUMMARY ===")
print(f"LEGIT (NTS backed by open defect): {tot_legit}")
print(f"MISMATCH (NTS but defect cleared):  {tot_clearedmismatch}")
print(f"ORPHAN (NTS, no defect row):        {tot_orphan}")
