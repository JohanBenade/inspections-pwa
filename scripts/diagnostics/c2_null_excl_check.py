import sqlite3
c = sqlite3.connect('/var/data/inspections.db'); c.row_factory = sqlite3.Row
TID = 'MONOGRAPH'
NULL_UNITS = ["014","015","016","227","252","269","248"]

for un in NULL_UNITS:
    u = c.execute("SELECT id FROM unit WHERE tenant_id=? AND unit_number=?", [TID, un]).fetchone()
    insp = c.execute("""SELECT id, cycle_id, exclusion_list_id FROM inspection
        WHERE unit_id=? AND tenant_id=? AND cycle_number=2
        ORDER BY created_at DESC LIMIT 1""", [u['id'], TID]).fetchone()
    # batch_unit rows for this unit + the C2 cycle
    bus = c.execute("""SELECT bu.batch_id, bu.exclusion_list_id, bu.status, ib.name
        FROM batch_unit bu LEFT JOIN inspection_batch ib ON ib.id=bu.batch_id
        WHERE bu.unit_id=? AND bu.cycle_id=? AND bu.tenant_id=?""",
        [u['id'], insp['cycle_id'], TID]).fetchall()
    print(f"\nUnit {un}: C2 insp.excl={insp['exclusion_list_id']}  cycle_id={insp['cycle_id']}")
    if not bus:
        print("   no batch_unit row for this cycle")
    for b in bus:
        elname = None
        if b['exclusion_list_id']:
            el = c.execute("SELECT name, item_count FROM exclusion_list WHERE id=?", [b['exclusion_list_id']]).fetchone()
            elname = f"{el['name']} ({el['item_count']} items)" if el else "(missing)"
        print(f"   batch {b['name']} | bu.excl={b['exclusion_list_id']} {('-> '+elname) if elname else ''} | status={b['status']}")
    # how many items actually skipped on this C2 inspection
    sk = c.execute("SELECT COUNT(*) n FROM inspection_item WHERE inspection_id=? AND status='skipped'", [insp['id']]).fetchone()['n']
    print(f"   skipped items on C2 inspection: {sk}")
