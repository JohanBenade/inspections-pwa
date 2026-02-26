import sqlite3, uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher

UNIT='158'; INSP_ID='mpho'; INSP_NAME='Mpho Mdluli'
DATE='2026-02-20'; TENANT='MONOGRAPH'; CYCLE='213a746f'

D=[
('522b4aeb','Floor tile has a hole under counter seating','NTS'),
('065b6eb7','Corners have gaps as indicated','NTS'),
('0740d3f1','Gasket forced into corner causing gap between gasket and window frame','NTS'),
('16e941da','Different white paint patch by window 1','NTS'),
('485aba2b','Gap between wall tiles and tile trim at sink splash back','NTS'),
('637c7b25','Gap between wall tiles and tile trim at top of stove splash back','NTS'),
('637c7b25','Tile trim at top of stove splash back has paint','NTS'),
('624544cd','Bin drawer is wobbly, unstable','NTS'),
('9d4b7503','Transparent silicon installed poorly under counter seating','NTS'),
('57c5f6a0','Plug cutout for microwave has grey paint','NTS'),
('7f7ddc15','Skirting under broom B.I.C is very skew','NTS'),
('c66e451c','Mixer is unstable when touched','NTS'),
('7414ad92','Gap between wall and DB','NTS'),
('7414ad92','DB cover is very loose','NTS'),
('6e557218','Gap between stove and top','NTS'),
('6e557218','Sealant between stove and top not installed','NI'),
('04796e27','Door is chipped by lockset','NTS'),
('afcc1bc2','Door frame is bent','NTS'),
('04796e27','Paint overlaps as indicated','NTS'),
('cc84d464','Lockset-cylinder and thumb turn is sticky','NTS'),
('e6f434e1','Rough plaster by study desk','NTS'),
('59a4040c','Paint has bubbles by study light','NTS'),
('59a4040c','Paint has bubbles by panel heater','NTS'),
('28999baf','Gap between wall and study desk plug','NTS'),
('28999baf','Paint is peeling off by study desk plug','NTS'),
('1ca36641','Sealant is cracking on B.I.C','NTS'),
('dc0e02ee','Green back wall has white paint inside B.I.C','NTS'),
('340d94a3','Door frame is bent','NTS'),
('b1f2960d','Two-tone paint on top of door','NTS'),
('80f75409','Residence lock handle sticks and gets stuck','NTS'),
('1e45af79','Gap between lockset and door','NTS'),
('d3eaba92','Green paint is peeling off inside B.I.C','NTS'),
('1136f030','White paint on skirting tile as indicated','NTS'),
('e2fd6318','Study desk light has paint droplets','NTS'),
('d3eaba92','Inside of B.I.C has green paint marks','NTS'),
('7b3e816b','Floating shelf is loose','NTS'),
('262bfbeb','White paint droplets on floating shelf','NTS'),
('9fdcd89e','Door frame is bent','NTS'),
('9fdcd89e','Paint peeling off on door frame','NTS'),
('9fdcd89e','Door frame has white marks','NTS'),
('9fdcd89e','Rough finish on door frame','NTS'),
('6a0771ae','Tile skirting has paint','NTS'),
('53a6348d','Two-tone paint above panel heater','NTS'),
('1fae2eac','Window frame has white paint droplets','NTS'),
('1fae2eac','Window handle rubs off powder coating on window frame','NTS'),
('5be0a265','Study desk light has paint droplets','NTS'),
('ef4935cb','Panel heater plug has paint droplets','NTS'),
('4e25adea','Paint on inside of B.I.C','NTS'),
('981e4097','Mortar on inside side of B.I.C','NTS'),
('0b929eb3','Gap between wall and floating shelf','NTS'),
('0b929eb3','Floating shelf is loose and unstable','NTS'),
('2f006892','Paint droplets on floating shelf','NTS'),
('c4a5aa6b','Paint droplets on top of study desk','NTS'),
('212d83e1','Poorly painted by lockset','NTS'),
('66cc0d36','Door frame has white paint','NTS'),
('66cc0d36','Two paints overlap on door frame','NTS'),
('bb4b4360','Lockset-cylinder and thumb turn are sticky','NTS'),
('04d2ad00','Signage has poorly wiped paint','NTS'),
('bd6a61c0','Green paint on wall has bubbles','NTS'),
('248d3871','White paint on wall has bubbles','NTS'),
('4a354d81','Window frame has white paint droplets','NTS'),
('f653cf83','Sealant between wall and floating shelf unfinished with holes','NTS'),
('b30c2d79','Paint droplets on top of study desk','NTS'),
('b6b5d166','Door has white paint marks','NTS'),
('4abe1624','Gap between tiled wall and airbrick above door','NTS'),
('df84942f','Tile trim on duct wall corner is cut halfway','NTS'),
('76c93f42','Tile is cut halfway on window sill','NTS'),
('347c7f63','Gap between tile and tile trim into window reveal','NTS'),
('7cd10dda','Airbrick in shower has mortar','NTS'),
('07d644a5','Sealant smudges on window frame finish','NTS'),
('f8fb4aed','Window sill/reveal is unfinished','NTS'),
('88b333f7','Shower floor to be tested if falls to trap','NTS'),
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
