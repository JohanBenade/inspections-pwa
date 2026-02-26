import sqlite3, uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

UNIT='154'; INSP_ID='mpho'; INSP_NAME='Mpho Mdluli'
DATE='2026-02-20'; TENANT='MONOGRAPH'; CYCLE='213a746f'

D=[
('522b4aeb','Chipped tile as indicated','NTS'),
('522b4aeb','Hollow tile as indicated','NTS'),
('3cf49a3d','Skirting has no grout under stove lockset and cabinets','NTS'),
('3cf49a3d','Tile skirting grout has white paint','NTS'),
('065b6eb7','Corners have gaps as indicated','NTS'),
('bfc0e3ab','Black marks on the white window frame','NTS'),
('7889a386','Gaps between tile and tile trims on window sill','NTS'),
('7889a386','Gap between tile trim and tiles by window 1a','NTS'),
('485aba2b','Gap between wall tiles and tile trim at sink splash back','NTS'),
('2aefb106','Pencil line on wall tile on sink splash back','NTS'),
('637c7b25','Bent tile trim at top of stove splash back','NTS'),
('637c7b25','Tile trim at top of stove splash back has paint','NTS'),
('624544cd','Bin drawer is wobbly, unstable','NTS'),
('82218345','Steel carcass is scratched on last drawer','NTS'),
('f2467f93','The last drawer is sandy','NTS'),
('09e5b0d4','Counter seating top balanced by cardboard underneath','NTS'),
('9d4b7503','Gaps on transparent silicon underneath counter seating','NTS'),
('5fe88982','Leg support on counter seating has white paint marks','NTS'),
('9d4b7503','Transparent silicon installed poorly under counter seating','NTS'),
('197ab3b2','Hanging electrical stove wire inside lockable pack','NTS'),
('7f7ddc15','Gap between boards inside broom B.I.C','NTS'),
('b35b9552','White paint droplets on broom cupboard','NTS'),
('6e557218','Gap between stove and top','NTS'),
('6e557218','Sealant between stove and top not installed','NI'),
('04796e27','Poorly painted on top of door','NTS'),
('04796e27','Door scratched on top right corner','NTS'),
('04796e27','Poorly painted by lockset','NTS'),
('afcc1bc2','Two paints overlap on door frame','NTS'),
('afcc1bc2','Paint created bubbles on door frame','NTS'),
('cc84d464','Lockset-cylinder and thumb turn is sticky','NTS'),
('14eb7511','No grout between tile skirting under wardrobe','NTS'),
('59a4040c','Green paint has patch not matching existing paint','NTS'),
('59a4040c','Green wall above floating shelf has white paint marks','NTS'),
('db6da547','Corner has gap on window frame as indicated','NTS'),
('5be0243e','Gasket is cut halfway','NTS'),
('5be0243e','Gasket is not glued','NTS'),
('1ca36641','Sealant cracking between B.I.C and wall','NTS'),
('dc0e02ee','Pencil line inside B.I.C sides next to hanger','NTS'),
('519d4580','Gap between floating shelf and B.I.C','NTS'),
('468ece9d','White paint marks on floating shelf','NTS'),
('5793d608','White paint marks on outside leaf of door','NTS'),
('b1f2960d','Poorly painted by lockset','NTS'),
('b1f2960d','Two-tone paint overlaps on door','NTS'),
('340d94a3','Door frame scratched paint peeling off','NTS'),
('340d94a3','Two-tone paint on top of door frame','NTS'),
('d1bfc830','Wall damaged by double plug under study desk','NTS'),
('2ed16ab7','Chipped floor tile next to B.I.C','NTS'),
('d58ea077','Bottom openable window is sticky','NTS'),
('09b9fc9b','Screw covers on handles not installed','NI'),
('09b9fc9b','Only 1 screw installed instead of two on window handle','NTS'),
('d3eaba92','Green back wall poorly painted inside B.I.C','NTS'),
('7b3e816b','Gaps between floating shelf and wall','NTS'),
('7b3e816b','Gaps between floating shelf and B.I.C','NTS'),
('80177e8e','Grey paint has two tones','NTS'),
('80177e8e','Two paints overlap on door','NTS'),
('80177e8e','Poorly painted by lockset','NTS'),
('9fdcd89e','Paint scratched on door frame','NTS'),
('ed6e3126','Door stopper has paint','NTS'),
('ed6e3126','Door stopper is loose','NTS'),
('85620ac4','Hollow tile as indicated','NTS'),
('1fae2eac','Window frame has white paint droplets','NTS'),
('5be0a265','Study desk light has paint droplets','NTS'),
('ef4935cb','Panel heater plug has paint droplets','NTS'),
('4e25adea','Back green wall has white paint inside B.I.C','NTS'),
('035a042f','B.I.C doors not aligning when closed','NTS'),
('0b929eb3','Gap between wall and floating shelf','NTS'),
('0b929eb3','Floating shelf is loose and unstable','NTS'),
('212d83e1','Door not fully painted on top','NTS'),
('212d83e1','Green paint peeling off on door','NTS'),
('66cc0d36','Screw popping out on door frame','NTS'),
('66cc0d36','Two paints overlap on door frame','NTS'),
('bb4b4360','Gap between door and lockset','NTS'),
('05c84b01','Wall damaged by pipe hole above door','NTS'),
('bd6a61c0','Green paint peeling off as indicated','NTS'),
('68d3f5a4','Hanging pipe on ceiling','NTS'),
('4a354d81','Window frame has white paint droplets','NTS'),
('07ad730b','Sealant showing white outlines on B.I.C','NTS'),
('07ad730b','Green wall showing white background inside B.I.C','NTS'),
('f653cf83','Gaps all around floating shelf','NTS'),
('4abe1624','Airbrick above door is loose','NTS'),
('e326b993','Door frame is bent','NTS'),
('e326b993','Paint peeling off on external leaf of door frame','NTS'),
('ebb584a4','B2B SS pull handle has paint','NTS'),
('c16fbe1e','Bathroom lock is sticky','NTS'),
('39fe1eda','WC indicator has paint and thumb turn is sticky','NTS'),
('a6939da2','D3 is sticky and gets stuck halfway','NTS'),
('3016c121','Tile trim on shower step is bent','NTS'),
('df84942f','Tile trim on duct wall is skew','NTS'),
('347c7f63','Gap between tiles and tile trim on window reveal','NTS'),
('7cd10dda','Gap between tiled wall and airbrick inside shower','NTS'),
('e2528889','Gaskets are loose','NTS'),
('8667f32c','WC is loose not fully fixed to floor','NTS'),
]

def gid(): return uuid.uuid4().hex[:8]
def now(): return datetime.now(timezone.utc).isoformat()
def fm(t,c,th=0.7):
    bm,bs=None,0
    tl=t.lower().strip()
    for x in c:
        s=SequenceMatcher(None,tl,x.lower().strip()).ratio()
        if s>bs: bs=s;bm=x
    return (bm,bs) if bs>=th else (None,0)

def wash(cur,tid,rd):
    cur.execute("SELECT ct.category_name FROM item_template it JOIN category_template ct ON it.category_id=ct.id WHERE it.id=?",(tid,))
    r=cur.fetchone(); cn=r[0] if r else 'UNKNOWN'
    cur.execute("SELECT description FROM defect_library WHERE tenant_id=? AND item_template_id=? ORDER BY usage_count DESC",(TENANT,tid))
    ie=[r[0] for r in cur.fetchall()]
    if ie:
        m,s=fm(rd,ie)
        if m: return m,f"item({s:.2f})",cn
    cur.execute("SELECT description FROM defect_library WHERE tenant_id=? AND category_name=? AND item_template_id IS NULL ORDER BY usage_count DESC",(TENANT,cn))
    ce=[r[0] for r in cur.fetchall()]
    if ce:
        m,s=fm(rd,ce)
        if m: return m,f"cat({s:.2f})",cn
    cl=rd.strip()
    if cl: cl=cl[0].upper()+cl[1:]
    return cl,"NEW",cn

def main():
    conn=sqlite3.connect('/var/data/inspections.db'); cur=conn.cursor(); n=now()
    print(f"=== IMPORT Unit {UNIT} | {INSP_NAME} | {DATE} | Cycle {CYCLE} ===\n")
    bad=False
    for t,r,d in D:
        cur.execute('SELECT id FROM item_template WHERE id=? AND tenant_id=?',(t,TENANT))
        if not cur.fetchone(): print(f"MISSING: {t} ({r})"); bad=True
    if bad: print("ABORTING"); conn.close(); return
    print(f"All {len(D)} template IDs verified\n")
    cur.execute('SELECT id FROM unit WHERE unit_number=? AND tenant_id=?',(UNIT,TENANT))
    uid=cur.fetchone()[0]; print(f"Unit ID: {uid}")
    cur.execute('SELECT id,status FROM inspection WHERE unit_id=? AND cycle_id=?',(uid,CYCLE))
    r=cur.fetchone()
    if r:
        iid=r[0]; print(f"Existing inspection: {iid} ({r[1]})")
        if r[1] not in('not_started','in_progress'): print("SKIP"); conn.close(); return
    else:
        iid=gid()
        cur.execute("INSERT INTO inspection(id,tenant_id,unit_id,cycle_id,inspection_date,inspector_id,inspector_name,status,started_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,'in_progress',?,?,?)",
            (iid,TENANT,uid,CYCLE,DATE,INSP_ID,INSP_NAME,n,n,n))
        print(f"Created inspection: {iid}")
    cur.execute("UPDATE inspection SET inspector_id=?,inspector_name=?,updated_at=? WHERE id=?",(INSP_ID,INSP_NAME,n,iid))
    cur.execute("UPDATE cycle_unit_assignment SET inspector_id=? WHERE cycle_id=? AND unit_id=?",(INSP_ID,CYCLE,uid))
    cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=?',(iid,))
    if cur.fetchone()[0]>0: print("Items exist already")
    else:
        cur.execute('SELECT id FROM item_template WHERE tenant_id=?',(TENANT,))
        ts=cur.fetchall()
        for t in ts: cur.execute("INSERT INTO inspection_item(id,tenant_id,inspection_id,item_template_id,status,marked_at) VALUES(?,?,?,?,'pending',NULL)",(gid(),TENANT,iid,t[0]))
        print(f"Created {len(ts)} inspection items")
    cur.execute("SELECT DISTINCT ii.item_template_id FROM inspection_item ii JOIN inspection i ON ii.inspection_id=i.id WHERE i.cycle_id=? AND ii.status='skipped' AND i.id!=?",(CYCLE,iid))
    ex=set(r[0] for r in cur.fetchall()); print(f"Exclusions: {len(ex)}")
    sk=0
    for e in ex:
        cur.execute("UPDATE inspection_item SET status='skipped',marked_at=? WHERE inspection_id=? AND item_template_id=?",(n,iid,e)); sk+=cur.rowcount
    print(f"Marked skipped: {sk}")
    cd=[]
    for t,r,d in D:
        if t in ex: print(f"DROPPED(excl): {r}")
        else: cd.append((t,r,d))
    nl=[]; dc=0
    for t,r,d in cd:
        w,ws,cn=wash(cur,t,r)
        if "NEW" in ws: nl.append((t,cn,w))
        print(f"  [{t}] {r} -> {w} [{ws}]")
        did=gid(); dt='not_installed' if d=='NI' else 'not_to_standard'
        cur.execute("INSERT INTO defect(id,tenant_id,unit_id,item_template_id,raised_cycle_id,defect_type,status,original_comment,created_at,updated_at) VALUES(?,?,?,?,?,?,'open',?,?,?)",
            (did,TENANT,uid,t,CYCLE,dt,w,n,n))
        cur.execute("UPDATE inspection_item SET status=?,comment=?,marked_at=? WHERE inspection_id=? AND item_template_id=?",(dt,w,n,iid,t))
        dc+=1
    print(f"\nDefects created: {dc}")
    cur.execute("UPDATE inspection_item SET status='ok',marked_at=? WHERE inspection_id=? AND status='pending'",(n,iid))
    print(f"Marked OK: {cur.rowcount}")
    for t,cn,ds in nl:
        cur.execute("INSERT INTO defect_library(id,tenant_id,category_name,item_template_id,description,usage_count,is_system,created_at) VALUES(?,?,?,?,?,1,0,?)",(gid(),TENANT,cn,t,ds,n))
    if nl: print(f"New library entries: {len(nl)}")
    cur.execute("UPDATE inspection SET status='submitted',submitted_at=?,updated_at=? WHERE id=?",(n,n,iid))
    cur.execute("UPDATE unit SET status='in_progress' WHERE id=? AND status='not_started'",(uid,))
    print("\n=== VERIFY ===")
    for s in['skipped','ok','not_to_standard','not_installed','pending']:
        cur.execute('SELECT COUNT(*) FROM inspection_item WHERE inspection_id=? AND status=?',(iid,s))
        print(f"{s}: {cur.fetchone()[0]}")
    cur.execute('SELECT COUNT(*) FROM defect WHERE unit_id=? AND raised_cycle_id=? AND status=?',(uid,CYCLE,'open'))
    print(f"defects: {cur.fetchone()[0]}")
    conn.commit(); print("\nCOMMITTED OK")
    conn.close()

if __name__=='__main__': main()
