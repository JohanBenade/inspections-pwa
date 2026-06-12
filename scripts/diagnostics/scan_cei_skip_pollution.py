import sqlite3
db=sqlite3.connect('/var/data/inspections.db'); db.row_factory=sqlite3.Row
def q(s,a=()): return db.execute(s,a).fetchall()
units=q("SELECT id,unit_number,floor FROM unit_real WHERE tenant_id='MONOGRAPH' AND unit_number NOT LIKE 'TEST%' ORDER BY CAST(unit_number AS INTEGER)")
suspect=[]
for u in units:
    cy=q("SELECT id,cycle_number,exclusion_list_id FROM inspection WHERE unit_id=? ORDER BY cycle_number ASC",(u['id'],))
    cur=cy[-1]
    if cur['exclusion_list_id']: continue   # has a list -> skips are legit
    prev=cy[-2] if len(cy)>1 else None
    fl=u['floor']
    rows=q("""SELECT it.floor_condition fc,
      (SELECT status FROM inspection_item WHERE inspection_id=? AND item_template_id=ii.item_template_id) prevst
      FROM inspection_item ii JOIN item_template it ON ii.item_template_id=it.id
      WHERE ii.inspection_id=? AND ii.status='skipped' AND ii.marked_at IS NULL""",
      (prev['id'] if prev else cur['id'],cur['id']))
    bad=0
    for r in rows:
        if fl and fl>0 and r['fc']=='ground_only': continue  # structural, legit
        bad+=1
    if bad>0: suspect.append((u['unit_number'],cur['cycle_number'],bad))
tot=sum(b for _,_,b in suspect)
print("=== SUSPECT: skipped-on-NULL-list (non-structural): %d units, %d items ==="%(len(suspect),tot))
for un,cyc,b in suspect: print("  %s C%d  %d"%(un,cyc,b))
