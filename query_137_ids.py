import sqlite3
conn = sqlite3.connect('/var/data/inspections.db')
cur = conn.cursor()

queries = [
    ("BEDROOM A BIC CHILDREN", "SELECT it.id, it.item_description FROM item_template it WHERE it.parent_item_id IN (SELECT it2.id FROM item_template it2 JOIN category_template ct ON it2.category_id=ct.id JOIN area_template at2 ON ct.area_id=at2.id WHERE at2.area_name='BEDROOM A' AND it2.item_description='B.I.C.' AND it2.tenant_id='MONOGRAPH') AND it.tenant_id='MONOGRAPH'"),
    ("BEDROOM B W3 CHILDREN", "SELECT it.id, it.item_description FROM item_template it WHERE it.parent_item_id IN (SELECT it2.id FROM item_template it2 JOIN category_template ct ON it2.category_id=ct.id JOIN area_template at2 ON ct.area_id=at2.id WHERE at2.area_name='BEDROOM B' AND it2.item_description='W3' AND it2.tenant_id='MONOGRAPH') AND it.tenant_id='MONOGRAPH'"),
    ("BEDROOM B ELECTRICAL", "SELECT it.id, it.item_description FROM item_template it JOIN category_template ct ON it.category_id=ct.id JOIN area_template at2 ON ct.area_id=at2.id WHERE at2.area_name='BEDROOM B' AND ct.category_name='ELECTRICAL' AND it.tenant_id='MONOGRAPH' AND it.depth>0"),
    ("BEDROOM B BIC CHILDREN", "SELECT it.id, it.item_description FROM item_template it WHERE it.parent_item_id IN (SELECT it2.id FROM item_template it2 JOIN category_template ct ON it2.category_id=ct.id JOIN area_template at2 ON ct.area_id=at2.id WHERE at2.area_name='BEDROOM B' AND it2.item_description='B.I.C.' AND it2.tenant_id='MONOGRAPH') AND it.tenant_id='MONOGRAPH'"),
    ("BEDROOM C CEILING", "SELECT it.id, it.item_description FROM item_template it JOIN category_template ct ON it.category_id=ct.id JOIN area_template at2 ON ct.area_id=at2.id WHERE at2.area_name='BEDROOM C' AND ct.category_name='CEILING' AND it.tenant_id='MONOGRAPH' AND it.depth>0"),
    ("BEDROOM C BIC CHILDREN", "SELECT it.id, it.item_description FROM item_template it WHERE it.parent_item_id IN (SELECT it2.id FROM item_template it2 JOIN category_template ct ON it2.category_id=ct.id JOIN area_template at2 ON ct.area_id=at2.id WHERE at2.area_name='BEDROOM C' AND it2.item_description='B.I.C.' AND it2.tenant_id='MONOGRAPH') AND it.tenant_id='MONOGRAPH'"),
    ("BATHROOM D3 CHILDREN", "SELECT it.id, it.item_description FROM item_template it WHERE it.parent_item_id IN (SELECT it2.id FROM item_template it2 JOIN category_template ct ON it2.category_id=ct.id JOIN area_template at2 ON ct.area_id=at2.id WHERE at2.area_name='BATHROOM' AND it2.item_description='D3' AND it2.tenant_id='MONOGRAPH') AND it.tenant_id='MONOGRAPH'"),
    ("KITCHEN SPLASH BACK ALL", "SELECT it.id, it.item_description, ct.category_name FROM item_template it JOIN category_template ct ON it.category_id=ct.id JOIN area_template at2 ON ct.area_id=at2.id WHERE at2.area_name='KITCHEN' AND ct.category_name LIKE '%SPLASH%' AND it.tenant_id='MONOGRAPH'"),
]

for label, sql in queries:
    print(f'=== {label} ===')
    cur.execute(sql)
    for r in cur.fetchall():
        print(f'  {" | ".join(str(x) for x in r)}')
    print()

conn.close()
