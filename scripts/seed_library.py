import sqlite3, uuid
from datetime import datetime, timezone

conn = sqlite3.connect('/var/data/inspections.db')
cur = conn.cursor()
now = datetime.now(timezone.utc).isoformat()

SEEDS = [
    ('BATHROOM','FF&E','mirror',['Cracked','Loose on wall','Not level','Scratched']),
    ('BATHROOM','FF&E','robe hook',['Loose','Not secured to wall','Damaged']),
    ('BATHROOM','FF&E','shelf under mirror',['Not level','Loose','Scratched']),
    ('BATHROOM','FF&E','toilet roll holder',['Loose','Not secured to wall','Damaged']),
    (None,'FF&E','Blind',['Not operating','Cord damaged','Not installed']),
    (None,'FF&E','Panel heater',['Not functioning','Not secured to wall','Thermostat not working']),
    (None,'FF&E','desk chair',['Wheels not working','Damaged','Scratched']),
    (None,'FF&E','mattress',['Stained','Damaged','Torn']),
    (None,'FF&E','single bed',['Frame damaged','Scratched','Not level']),
    (None,'FF&E','towel rail',['Loose','Not level','Not secured to wall']),
    (None,'FF&E','robe hook',['Loose','Not secured to wall','Damaged']),
    ('KITCHEN','FF&E','Fridge',['Door not closing properly','Handle damaged','Scratched','Not functioning']),
    ('KITCHEN','FF&E','microwave',['Not functioning','Door not closing properly','Damaged','Interior not clean']),
    ('KITCHEN','FF&E','bronx kitchen stools',['Scratched','Damaged','Not level']),
    ('KITCHEN','FF&E','broom',['Not supplied','Damaged']),
    ('KITCHEN','FF&E','mop',['Not supplied','Damaged']),
    ('KITCHEN','FF&E','dust pan',['Not supplied','Damaged']),
    ('KITCHEN','FF&E','fire blanket',['Not installed','Bracket damaged']),
    ('KITCHEN','FF&E','flip top bin',['Lid damaged','Mechanism not working']),
    ('KITCHEN','FF&E','towel rail at sink',['Loose','Not level','Not secured to wall']),
    ('KITCHEN','DOORS','D1 & D1a leaf',['Damaged paint as indicated','Scratched as indicated']),
    ('KITCHEN','DOORS','finished all round',['Paint not finished as indicated','Touch-up required']),
    ('KITCHEN','DOORS','Plastered recess',['Plaster cracked','Paint damaged as indicated']),
    ('KITCHEN','DOORS','Ironmongery',['Missing','Damaged','Loose']),
    (None,'DOORS','lockset',['Not functioning','Cylinder damaged','Key not working','Thumb turn stiff']),
    ('KITCHEN','DOORS','Frame',['Scratched as indicated','Paint stains as indicated']),
    (None,'PLUMBING','hot water',['No hot water','Slow to heat','Temperature inconsistent']),
    ('LOUNGE','ELECTRICAL','Wi-Fi repeater',['Not functioning','Not installed','No signal']),
]

added = 0
for area, cat, match, defects in SEEDS:
    if area:
        cur.execute("SELECT DISTINCT it.id FROM item_template it JOIN category_template ct ON it.category_id=ct.id JOIN area_template at ON ct.area_id=at.id WHERE ct.category_name=? AND at.area_name=? AND it.item_description LIKE ? AND it.tenant_id='MONOGRAPH'",(cat,area,'%'+match+'%'))
    else:
        cur.execute("SELECT DISTINCT it.id FROM item_template it JOIN category_template ct ON it.category_id=ct.id WHERE ct.category_name=? AND it.item_description LIKE ? AND it.tenant_id='MONOGRAPH'",(cat,'%'+match+'%'))
    for (tid,) in cur.fetchall():
        for desc in defects:
            cur.execute("SELECT id FROM defect_library WHERE item_template_id=? AND description=? AND tenant_id='MONOGRAPH'",(tid,desc))
            if cur.fetchone(): continue
            cur.execute("INSERT INTO defect_library (id,tenant_id,category_name,item_template_id,description,usage_count,is_system,created_at) VALUES (?,'MONOGRAPH',?,?,?,0,1,?)",(uuid.uuid4().hex[:8],cat,tid,desc,now))
            added += 1

conn.commit()
print(f'Added: {added}')

# Verify
cur.execute("SELECT DISTINCT ii.item_template_id FROM inspection_item ii JOIN inspection i ON ii.inspection_id=i.id WHERE i.cycle_id='792812c7' AND ii.status='skipped'")
excluded = [r[0] for r in cur.fetchall()]
empty = 0
for tid in excluded:
    cur.execute("SELECT COUNT(*) FROM defect_library WHERE item_template_id=? AND tenant_id='MONOGRAPH'",(tid,))
    if cur.fetchone()[0]==0:
        cur.execute("SELECT it.item_description,ct.category_name,at.area_name FROM item_template it JOIN category_template ct ON it.category_id=ct.id JOIN area_template at ON ct.area_id=at.id WHERE it.id=?",(tid,))
        r=cur.fetchone()
        if r: print(f'  STILL EMPTY: {r[2]}>{r[1]}>{r[0]}')
        empty+=1

print(f'Covered: {len(excluded)-empty}/86, Still empty: {empty}')
conn.close()
