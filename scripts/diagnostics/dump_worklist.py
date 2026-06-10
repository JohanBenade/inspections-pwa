import sqlite3, csv
c = sqlite3.connect('/var/data/inspections.db'); c.row_factory = sqlite3.Row
TEN='MONOGRAPH'
nums='248 250 014 015 016 023 227 027 028 029 030 031 032 035 036 037 038 039 040 130 131 132 133 134 135 136 137 138 139 140 141 142 143 230 231 233 235 236 237 239 241 243 042 045 046 047 049 050 051 052 148 149 150 151 152 153 156 157 159 252 257 053 054 055 056 057 163 264 269'.split()
units=c.execute("SELECT unit_number un,id,block,floor FROM unit WHERE tenant_id=? AND unit_number IN (%s)"%','.join('?'*len(nums)),[TEN]+nums).fetchall()

rows=[]
for u in units:
    fl=u['floor']
    insp=c.execute("SELECT id,cycle_number,status FROM inspection WHERE unit_id=? ORDER BY cycle_number DESC, started_at DESC LIMIT 1",[u['id']]).fetchone()
    fc="('all','ground_only')" if fl==0 else "('all')"
    q="""SELECT at.area_name area, ct.category_name cat, it.item_description item,
      ii.status st, cei.reason skipreason
      FROM inspection_item ii
      JOIN item_template it ON it.id=ii.item_template_id
      JOIN category_template ct ON ct.id=it.category_id
      JOIN area_template at ON at.id=ct.area_id
      LEFT JOIN cycle_excluded_item cei ON cei.cycle_id=(SELECT cycle_id FROM inspection WHERE id=ii.inspection_id)
        AND cei.item_template_id=it.id
      WHERE ii.inspection_id=? AND it.active=1 AND it.floor_condition IN %s
        AND ii.status!='ok'
      ORDER BY at.area_order, ct.category_order, it.item_order"""%fc
    for r in c.execute(q,(insp['id'],)):
        rows.append([u['un'],u['block'],fl,'C%d'%insp['cycle_number'],insp['status'],
            r['area'],r['cat'],r['item'],r['st'],r['skipreason'] or ''])

with open('/tmp/worklist.csv','w',newline='') as f:
    w=csv.writer(f)
    w.writerow(['Unit','Block','Floor','Cycle','InspStatus','Area','Category','Item','ItemStatus','SkipReason'])
    w.writerows(rows)
print('rows written:',len(rows))
