import sqlite3
conn = sqlite3.connect('/var/data/inspections.db')
cur = conn.cursor()

queries = [
    ("BROOM CUPBOARD CHILDREN", "SELECT it.id, it.item_description FROM item_template it WHERE it.parent_item_id IN (SELECT it2.id FROM item_template it2 JOIN category_template ct ON it2.category_id=ct.id JOIN area_template at2 ON ct.area_id=at2.id WHERE at2.area_name='KITCHEN' AND it2.item_description='Broom cupboard' AND it2.tenant_id='MONOGRAPH') AND it.tenant_id='MONOGRAPH'"),
    ("BEDROOM C FRAME CHILDREN", "SELECT it.id, it.item_description FROM item_template it WHERE it.parent_item_id IN (SELECT it2.id FROM item_template it2 JOIN category_template ct ON it2.category_id=ct.id JOIN area_template at2 ON ct.area_id=at2.id WHERE at2.area_name='BEDROOM C' AND ct.category_name='DOORS' AND it2.item_description='Frame' AND it2.tenant_id='MONOGRAPH') AND it.tenant_id='MONOGRAPH'"),
    ("BEDROOM D ELECTRICAL", "SELECT it.id, it.item_description FROM item_template it JOIN category_template ct ON it.category_id=ct.id JOIN area_template at2 ON ct.area_id=at2.id WHERE at2.area_name='BEDROOM D' AND ct.category_name='ELECTRICAL' AND it.tenant_id='MONOGRAPH' AND it.depth>0"),
    ("BEDROOM D BIC CHILDREN", "SELECT it.id, it.item_description FROM item_template it WHERE it.parent_item_id IN (SELECT it2.id FROM item_template it2 JOIN category_template ct ON it2.category_id=ct.id JOIN area_template at2 ON ct.area_id=at2.id WHERE at2.area_name='BEDROOM D' AND it2.item_description='B.I.C.' AND it2.tenant_id='MONOGRAPH') AND it.tenant_id='MONOGRAPH'"),
    ("BATHROOM SHR ARM", "SELECT it.id, it.item_description FROM item_template it JOIN category_template ct ON it.category_id=ct.id JOIN area_template at2 ON ct.area_id=at2.id WHERE at2.area_name='BATHROOM' AND ct.category_name='PLUMBING' AND it.tenant_id='MONOGRAPH' AND it.item_description LIKE '%install%'"),
]

for label, sql in queries:
    print(f'=== {label} ===')
    cur.execute(sql)
    for r in cur.fetchall():
        print(f'  {r[0]} | {r[1]}')
    print()

conn.close()
