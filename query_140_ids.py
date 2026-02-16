import sqlite3
conn = sqlite3.connect('/var/data/inspections.db')
cur = conn.cursor()

queries = [
    ("KITCHEN W1a CHILDREN", "SELECT it.id, it.item_description FROM item_template it WHERE it.parent_item_id IN (SELECT it2.id FROM item_template it2 JOIN category_template ct ON it2.category_id=ct.id JOIN area_template at2 ON ct.area_id=at2.id WHERE at2.area_name='KITCHEN' AND it2.item_description='W1a' AND it2.tenant_id='MONOGRAPH') AND it.tenant_id='MONOGRAPH'"),
    ("BEDROOM B STUDY DESK CHILDREN", "SELECT it.id, it.item_description FROM item_template it WHERE it.parent_item_id IN (SELECT it2.id FROM item_template it2 JOIN category_template ct ON it2.category_id=ct.id JOIN area_template at2 ON ct.area_id=at2.id WHERE at2.area_name='BEDROOM B' AND it2.item_description='Study desk' AND it2.tenant_id='MONOGRAPH') AND it.tenant_id='MONOGRAPH'"),
    ("BEDROOM D FLOATING SHELF CHILDREN", "SELECT it.id, it.item_description FROM item_template it WHERE it.parent_item_id IN (SELECT it2.id FROM item_template it2 JOIN category_template ct ON it2.category_id=ct.id JOIN area_template at2 ON ct.area_id=at2.id WHERE at2.area_name='BEDROOM D' AND it2.item_description='Floating shelf' AND it2.tenant_id='MONOGRAPH') AND it.tenant_id='MONOGRAPH'"),
    ("BATHROOM PLUMBING SHR ALL", "SELECT it.id, it.item_description, COALESCE(p.item_description,'') FROM item_template it LEFT JOIN item_template p ON it.parent_item_id=p.id JOIN category_template ct ON it.category_id=ct.id JOIN area_template at2 ON ct.area_id=at2.id WHERE at2.area_name='BATHROOM' AND ct.category_name='PLUMBING' AND it.tenant_id='MONOGRAPH' AND it.depth>0"),
]

for label, sql in queries:
    print(f'=== {label} ===')
    cur.execute(sql)
    for r in cur.fetchall():
        print(f'  {" | ".join(str(x) for x in r)}')
    print()

conn.close()
