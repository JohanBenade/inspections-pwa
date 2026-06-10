import sqlite3
c=sqlite3.connect('/var/data/inspections.db');c.row_factory=sqlite3.Row
for un in ['014','015','016','227']:
    u=c.execute("SELECT id,floor FROM unit WHERE tenant_id='MONOGRAPH' AND unit_number=?",(un,)).fetchone()
    # ALL inspections for this unit, newest first
    insps=c.execute("SELECT id,cycle_number,status,inspection_date,started_at,review_submitted_at FROM inspection WHERE unit_id=? ORDER BY cycle_number DESC,started_at DESC",(u['id'],)).fetchall()
    print('=== UNIT',un,'floor',u['floor'],'===')
    for i in insps:
        print('  insp',i['id'][:8],'C%d'%i['cycle_number'],i['status'],'date',i['inspection_date'],'rev',i['review_submitted_at'])
    latest=insps[0]
    fc="('all','ground_only')" if u['floor']==0 else "('all')"
    q="""SELECT at.area_name ar, ct.category_name ca, it.item_description d, ii.status, ii.marked_at, ii.comment
      FROM inspection_item ii JOIN item_template it ON it.id=ii.item_template_id
      JOIN category_template ct ON ct.id=it.category_id JOIN area_template at ON at.id=ct.area_id
      WHERE ii.inspection_id=? AND it.active=1 AND it.floor_condition IN %s
        AND ii.status IN ('not_to_standard','not_installed')
      ORDER BY ii.marked_at"""%fc
    nts=c.execute(q,(latest['id'],)).fetchall()
    print('  NTS/nINST on latest C%d (%s):'%(latest['cycle_number'],latest['id'][:8]))
    for n in nts:
        print('    [%s] %s/%s/%s | marked_at=%s | %s'%(n['status'],n['ar'],n['ca'],n['d'],n['marked_at'],(n['comment'] or '')[:40]))
