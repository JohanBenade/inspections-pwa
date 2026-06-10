import sqlite3
from collections import defaultdict
c = sqlite3.connect('/var/data/inspections.db'); c.row_factory = sqlite3.Row
TEN='MONOGRAPH'
ALLF=c.execute("SELECT COUNT(*) FROM item_template WHERE active=1 AND floor_condition='all'").fetchone()[0]
GND =c.execute("SELECT COUNT(*) FROM item_template WHERE active=1 AND floor_condition='ground_only'").fetchone()[0]
def denom(fl): return (ALLF+GND) if fl==0 else ALLF
print('denom GF',ALLF+GND,'aboveGF',ALLF)

nums='248 250 014 015 016 023 227 027 028 029 030 031 032 035 036 037 038 039 040 130 131 132 133 134 135 136 137 138 139 140 141 142 143 230 231 233 235 236 237 239 241 243 042 045 046 047 049 050 051 052 148 149 150 151 152 153 156 157 159 252 257 053 054 055 056 057 163 264 269'.split()
units=c.execute("SELECT unit_number un,id,block,floor FROM unit WHERE tenant_id=? AND unit_number IN (%s)"%','.join('?'*len(nums)),[TEN]+nums).fetchall()

res=[]
for u in units:
    # highest cycle_number inspection for this unit
    insp=c.execute("SELECT id,cycle_number,status FROM inspection WHERE unit_id=? ORDER BY cycle_number DESC, started_at DESC LIMIT 1",[u['id']]).fetchone()
    sb=defaultdict(int)
    for r in c.execute("SELECT status,COUNT(*) n FROM inspection_item WHERE inspection_id=? GROUP BY status",[insp['id']]):
        sb[r['status']]=r['n']
    dn=denom(u['floor'])
    ok=sb.get('ok',0)
    need=dn-ok
    res.append(dict(un=u['un'],block=u['block'],floor=u['floor'],cyc=insp['cycle_number'],
        st=insp['status'],dn=dn,ok=ok,need=need,
        pend=sb.get('pending',0),nts=sb.get('not_to_standard',0),
        ninst=sb.get('not_installed',0),skip=sb.get('skipped',0)))

res.sort(key=lambda x:(x['block'],x['floor'],x['un']))
print('UNIT BLK FL C St    denom  ok  need | pend nts ninst skip')
zt=defaultdict(lambda:[0,0]); gt=[0,0]
cz=None
for r in res:
    z=(r['block'],r['floor'])
    if cz and z!=cz:
        print('  -- zone %s F%s subtotal: need=%d (units=%d)'%(cz[0],cz[1],zt[cz][0],zt[cz][1]))
    cz=z
    zt[z][0]+=r['need']; zt[z][1]+=1; gt[0]+=r['need']; gt[1]+=1
    print('%-4s %-7s %d C%d %-4s %4d %4d %4d | %3d %3d %3d %3d'%(
        r['un'],r['block'],r['floor'],r['cyc'],r['st'][:4],r['dn'],r['ok'],r['need'],
        r['pend'],r['nts'],r['ninst'],r['skip']))
print('  -- zone %s F%s subtotal: need=%d (units=%d)'%(cz[0],cz[1],zt[cz][0],zt[cz][1]))
print('=== GRAND: need_MS total=%d across %d units ==='%(gt[0],gt[1]))
