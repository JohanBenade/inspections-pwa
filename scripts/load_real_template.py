import sqlite3, uuid, copy

def gen_id():
    return uuid.uuid4().hex[:12]

conn = sqlite3.connect('/var/data/inspections.db')
cur = conn.cursor()
tenant_id = 'MONOGRAPH'

print('Clearing...')
cur.execute('DELETE FROM inspection_item')
cur.execute('DELETE FROM item_template')
cur.execute('DELETE FROM category_template')
cur.execute('DELETE FROM area_template')
conn.commit()

bc = {'DOORS': {'o': 1, 'i': [{'n': 'Door leaf', 'c': ['finished all round']}, {'n': 'Frame', 'c': ['hinges', 'finish', 'striker plate']}, {'n': 'Ironmongery', 'c': ['handle', 'lockset', 'door stop']}]}, 'WALLS': {'o': 2, 'i': [{'n': 'smooth plaster', 'c': []}, {'n': 'paint - orchid bay', 'c': []}]}, 'WINDOWS': {'o': 3, 'i': [{'n': 'Window', 'c': ['frame & coating', 'glass', 'hinges', 'gaskets', 'operation', 'burglar bars', 'sill']}]}, 'FLOOR': {'o': 4, 'i': [{'n': 'Floor tile set out', 'c': []}, {'n': 'chipped/broken/hollow tiles', 'c': []}, {'n': 'grout dove grey', 'c': []}, {'n': 'tile skirting', 'c': []}]}, 'CEILING': {'o': 5, 'i': [{'n': 'paint - orchid bay', 'c': []}]}, 'ELECTRICAL': {'o': 6, 'i': [{'n': 'ceiling mounted light', 'c': []}, {'n': 'double plug', 'c': []}, {'n': 'light switch', 'c': []}]}, 'JOINERY': {'o': 7, 'i': [{'n': 'B.I.C.', 'c': ['carcass', 'doors', 'handles', 'shelves', 'hanging rail', 'door stop']}, {'n': 'Study desk', 'c': ['top', 'finish', 'edge']}]}, 'FF&E': {'o': 8, 'i': [{'n': 'Bed frame', 'c': []}, {'n': 'Mattress', 'c': []}, {'n': 'Desk chair', 'c': []}]}}

td = {'KITCHEN': {'o': 1, 'cats': {'DOORS': {'o': 1, 'i': [{'n': 'D1 & D1a leaf', 'c': ['finished all round']}, {'n': 'Frame', 'c': ['hinges', 'finish', 'striker plate']}, {'n': 'Ironmongery', 'c': ['handle', 'lockset', 'kickplate', 'door stop', 'door closer']}]}, 'WALLS': {'o': 2, 'i': [{'n': 'smooth plaster', 'c': []}, {'n': 'paint - orchid bay', 'c': []}, {'n': 'Splash back at sink', 'c': ['tile trim', 'grout dove grey', 'chipped/broken/hollow tiles']}]}, 'WINDOWS': {'o': 3, 'i': [{'n': 'W1', 'c': ['frame & coating', 'glass', 'hinges', 'gaskets', 'operation', 'burglar bars', 'sill']}, {'n': 'W1a', 'c': ['frame & coating', 'glass', 'hinges', 'gaskets', 'operation', 'burglar bars', 'sill']}]}, 'FLOOR': {'o': 4, 'i': [{'n': 'Floor tile set out', 'c': []}, {'n': 'chipped/broken/hollow tiles', 'c': []}, {'n': 'grout dove grey', 'c': []}, {'n': 'tile skirting', 'c': []}]}, 'CEILING': {'o': 5, 'i': [{'n': 'paint - orchid bay', 'c': []}]}, 'ELECTRICAL': {'o': 6, 'i': [{'n': 'DB', 'c': []}, {'n': 'Wi-Fi repeater', 'c': []}, {'n': 'ceiling mounted light', 'c': []}, {'n': 'fridge double plug', 'c': []}, {'n': 'stove isolator', 'c': []}]}, 'PLUMBING': {'o': 7, 'i': [{'n': 'Sink', 'c': ['mixer', 'waste', 'trap', 'angel valves', 'silicone']}]}, 'JOINERY': {'o': 8, 'i': [{'n': 'Sink pack', 'c': ['carcass', 'doors', 'handles', 'shelves']}, {'n': 'Bin drawer', 'c': ['carcass', 'drawer', 'handles', 'runner']}, {'n': 'Lockable pack 1&2', 'c': ['carcass', 'doors', 'handles', 'locks']}, {'n': 'Lockable pack 3&4', 'c': ['carcass', 'doors', 'handles', 'locks']}, {'n': 'Broom cupboard', 'c': ['carcass', 'doors', 'handles', 'shelves']}, {'n': 'Counter top', 'c': ['finish', 'edge', 'silicone']}]}, 'FF&E': {'o': 9, 'i': [{'n': 'Stove', 'c': ['installation', 'operation', 'control panel']}, {'n': 'Extractor', 'c': ['installation', 'operation']}, {'n': 'Fire blanket', 'c': []}]}}}, 'LOUNGE': {'o': 2, 'cats': {'DOORS': {'o': 1, 'i': [{'n': 'D2 leaf', 'c': ['finished all round']}, {'n': 'Frame', 'c': ['hinges', 'finish', 'striker plate']}, {'n': 'Ironmongery', 'c': ['handle', 'lockset', 'door stop']}]}, 'WALLS': {'o': 2, 'i': [{'n': 'smooth plaster', 'c': []}, {'n': 'paint - orchid bay', 'c': []}]}, 'WINDOWS': {'o': 3, 'i': [{'n': 'W2', 'c': ['frame & coating', 'glass', 'hinges', 'gaskets', 'operation', 'burglar bars', 'sill']}]}, 'FLOOR': {'o': 4, 'i': [{'n': 'Floor tile set out', 'c': []}, {'n': 'chipped/broken/hollow tiles', 'c': []}, {'n': 'grout dove grey', 'c': []}, {'n': 'tile skirting', 'c': []}]}, 'CEILING': {'o': 5, 'i': [{'n': 'paint - orchid bay', 'c': []}]}, 'ELECTRICAL': {'o': 6, 'i': [{'n': 'ceiling mounted light', 'c': []}, {'n': 'double plug', 'c': []}, {'n': 'TV point', 'c': []}, {'n': 'light switch', 'c': []}]}, 'PLUMBING': {'o': 7, 'i': [{'n': 'Geyser', 'c': ['unit & insulation', 'pipes & valves', 'drain & trap']}]}, 'JOINERY': {'o': 8, 'i': [{'n': 'TV unit', 'c': ['carcass', 'doors', 'handles', 'shelves']}]}, 'FF&E': {'o': 9, 'i': [{'n': 'Couch', 'c': []}, {'n': 'Coffee table', 'c': []}]}}}, 'BATHROOM': {'o': 3, 'cats': {'DOORS': {'o': 1, 'i': [{'n': 'D3 leaf', 'c': ['finished all round']}, {'n': 'Frame', 'c': ['hinges', 'finish', 'striker plate']}, {'n': 'Ironmongery', 'c': ['handle', 'bathroom lock', 'B2B SS pull handle', 'door stop']}, {'n': 'Airbrick above door', 'c': []}]}, 'WALLS': {'o': 2, 'i': [{'n': 'smooth plaster', 'c': []}, {'n': 'paint - orchid bay', 'c': []}, {'n': 'Wall tiles', 'c': ['tile trim', 'grout dove grey', 'chipped/broken/hollow tiles']}]}, 'WINDOWS': {'o': 3, 'i': [{'n': 'W3', 'c': ['frame & coating', 'glass', 'hinges', 'gaskets', 'operation', 'sill']}]}, 'FLOOR': {'o': 4, 'i': [{'n': 'Floor tile set out', 'c': []}, {'n': 'chipped/broken/hollow tiles', 'c': []}, {'n': 'grout dove grey', 'c': []}, {'n': 'floor waste', 'c': []}]}, 'CEILING': {'o': 5, 'i': [{'n': 'paint - orchid bay', 'c': []}]}, 'ELECTRICAL': {'o': 6, 'i': [{'n': 'ceiling mounted light', 'c': []}, {'n': 'shaver plug', 'c': []}, {'n': 'light switch', 'c': []}, {'n': 'extractor fan', 'c': []}]}, 'PLUMBING': {'o': 7, 'i': [{'n': 'Toilet', 'c': ['pan', 'seat', 'cistern', 'flush mechanism', 'silicone']}, {'n': 'Basin', 'c': ['basin', 'mixer', 'waste', 'trap', 'silicone']}, {'n': 'Shower', 'c': ['mixer', 'arm & rose', 'waste', 'door/screen', 'silicone', 'control panel']}]}, 'JOINERY': {'o': 8, 'i': [{'n': 'Vanity', 'c': ['carcass', 'doors', 'handles', 'counter top']}, {'n': 'Mirror', 'c': []}]}, 'FF&E': {'o': 9, 'i': [{'n': 'Toilet roll holder', 'c': []}, {'n': 'Towel rail', 'c': []}]}}}}

for i, nm in enumerate(['BEDROOM A', 'BEDROOM B', 'BEDROOM C', 'BEDROOM D'], 4):
    td[nm] = {'o': i, 'cats': copy.deepcopy(bc)}

# Columns: id, tenant_id, category_id, parent_item_id, item_description, item_order, depth
for an, ad in td.items():
    aid = gen_id()
    cur.execute('INSERT INTO area_template VALUES (?,?,?,?,?)', [aid, tenant_id, an, ad['o'], 'standard'])
    for cn, cd in ad['cats'].items():
        cid = gen_id()
        cur.execute('INSERT INTO category_template VALUES (?,?,?,?,?)', [cid, tenant_id, aid, cn, cd['o']])
        io = 1
        for it in cd['i']:
            pid = gen_id()
            # parent: depth=0
            cur.execute('INSERT INTO item_template (id, tenant_id, category_id, parent_item_id, item_description, item_order, depth) VALUES (?,?,?,?,?,?,?)', [pid, tenant_id, cid, None, it['n'], io, 0])
            io += 1
            for ch in it['c']:
                # child: depth=1
                cur.execute('INSERT INTO item_template (id, tenant_id, category_id, parent_item_id, item_description, item_order, depth) VALUES (?,?,?,?,?,?,?)', [gen_id(), tenant_id, cid, pid, ch, io, 1])
                io += 1

conn.commit()
cur.execute('SELECT COUNT(*) FROM item_template')
print(f'Done! Items: {cur.fetchone()[0]}')
cur.execute('SELECT area_name FROM area_template ORDER BY area_order')
print([r[0] for r in cur.fetchall()])
conn.close()
