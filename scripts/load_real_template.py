"""Load real inspection template (representative ~250 items)"""
import sqlite3
import os
import uuid
import copy

def gen_id():
    return uuid.uuid4().hex[:12]

def main():
    db_path = os.environ.get('DATABASE_PATH', 'data/inspections.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT id FROM tenant LIMIT 1")
    tenant_id = cur.fetchone()['id']
    print(f"Tenant ID: {tenant_id}")

    print("\nClearing existing template...")
    cur.execute("DELETE FROM inspection_item")
    cur.execute("DELETE FROM item_template")
    cur.execute("DELETE FROM category_template")
    cur.execute("DELETE FROM area_template")
    conn.commit()

    template_data = {
        "KITCHEN": {"order": 1, "categories": {
            "DOORS": {"order": 1, "items": [
                {"name": "D1 & D1a leaf", "children": ["finished all round"]},
                {"name": "Frame", "children": ["hinges", "finish", "striker plate"]},
                {"name": "Ironmongery", "children": ["handle", "lockset - cylinder and thumb turn", "kickplate", "master key", "door stop", "door closer"]},
                {"name": "Plastered recess above door", "children": ["finish", "unit signage"]},
                {"name": "Face brick sill", "children": []},
                {"name": "soft joint between tile and brick", "children": []},
            ]},
            "WALLS": {"order": 2, "items": [
                {"name": "smooth plaster", "children": []},
                {"name": "paint - orchid bay", "children": []},
                {"name": "Splash back at sink", "children": ["tile trim at window 1a", "tile into window sill", "splash back wrap at sink", "tile trim at sink splash back", "grout dove grey", "chipped/broken/hollow tiles"]},
                {"name": "Stove splash back", "children": ["tile trim at top and side", "grout dove grey", "chipped/broken/hollow tiles"]},
            ]},
            "WINDOWS": {"order": 3, "items": [
                {"name": "W1", "children": ["frame & coating", "glass", "hinges", "gaskets", "operation", "burglar bars", "sill"]},
                {"name": "W1a", "children": ["frame & coating", "glass", "hinges", "gaskets", "operation", "burglar bars", "sill"]},
            ]},
            "FLOOR": {"order": 4, "items": [
                {"name": "Floor tile set out", "children": []},
                {"name": "Soft joint cross", "children": []},
                {"name": "chipped/broken/hollow tiles", "children": []},
                {"name": "grout dove grey", "children": []},
                {"name": "tile skirting", "children": []},
            ]},
            "CEILING": {"order": 5, "items": [
                {"name": "paint - orchid bay", "children": []},
                {"name": "plaster recess", "children": []},
            ]},
            "ELECTRICAL": {"order": 6, "items": [
                {"name": "DB", "children": []},
                {"name": "fluorescent led x 2 bulbs", "children": []},
                {"name": "Wi-Fi repeater", "children": []},
                {"name": "ceiling mounted light x 2 bulbs", "children": []},
                {"name": "fridge double plug", "children": []},
                {"name": "double plug at counter", "children": []},
                {"name": "stove isolator", "children": []},
                {"name": "extractor switch", "children": []},
                {"name": "light switch single", "children": []},
            ]},
            "PLUMBING": {"order": 7, "items": [
                {"name": "Sink", "children": ["mixer", "waste", "trap", "angel valves", "silicone"]},
            ]},
            "JOINERY": {"order": 8, "items": [
                {"name": "Sink pack", "children": ["carcass", "doors", "drawer", "handles", "shelves"]},
                {"name": "Bin drawer", "children": ["carcass", "drawer", "handles", "runner"]},
                {"name": "Lockable pack 1&2", "children": ["carcass", "doors", "handles", "shelves", "locks"]},
                {"name": "Lockable pack 3&4", "children": ["carcass", "doors", "handles", "shelves", "locks"]},
                {"name": "Broom cupboard", "children": ["carcass", "doors", "handles", "shelves"]},
                {"name": "Counter top", "children": ["finish", "edge", "silicone"]},
                {"name": "Seating ledge", "children": ["finish", "edge"]},
            ]},
            "FF&E": {"order": 9, "items": [
                {"name": "Stove", "children": ["installation", "operation", "control panel"]},
                {"name": "Extractor", "children": ["installation", "operation", "filters"]},
                {"name": "Fire blanket", "children": []},
            ]},
        }},
        "LOUNGE": {"order": 2, "categories": {
            "DOORS": {"order": 1, "items": [
                {"name": "D2 leaf", "children": ["finished all round"]},
                {"name": "Frame", "children": ["hinges", "finish", "striker plate"]},
                {"name": "Ironmongery", "children": ["handle", "lockset", "door stop"]},
            ]},
            "WALLS": {"order": 2, "items": [
                {"name": "smooth plaster", "children": []},
                {"name": "paint - orchid bay", "children": []},
            ]},
            "WINDOWS": {"order": 3, "items": [
                {"name": "W2", "children": ["frame & coating", "glass", "hinges", "gaskets", "operation", "burglar bars", "sill"]},
            ]},
            "FLOOR": {"order": 4, "items": [
                {"name": "Floor tile set out", "children": []},
                {"name": "Soft joint cross", "children": []},
                {"name": "chipped/broken/hollow tiles", "children": []},
                {"name": "grout dove grey", "children": []},
                {"name": "tile skirting", "children": []},
            ]},
            "CEILING": {"order": 5, "items": [
                {"name": "paint - orchid bay", "children": []},
            ]},
            "ELECTRICAL": {"order": 6, "items": [
                {"name": "ceiling mounted light", "children": []},
                {"name": "double plug", "children": []},
                {"name": "TV point", "children": []},
                {"name": "light switch", "children": []},
            ]},
            "PLUMBING": {"order": 7, "items": [
                {"name": "Geyser", "children": ["unit & insulation", "pipes & valves", "drain & trap"]},
            ]},
            "JOINERY": {"order": 8, "items": [
                {"name": "TV unit", "children": ["carcass", "doors", "handles", "shelves"]},
            ]},
            "FF&E": {"order": 9, "items": [
                {"name": "Couch", "children": []},
                {"name": "Coffee table", "children": []},
            ]},
        }},
        "BATHROOM": {"order": 3, "categories": {
            "DOORS": {"order": 1, "items": [
                {"name": "D3 leaf", "children": ["finished all round"]},
                {"name": "Frame", "children": ["hinges", "finish", "striker plate"]},
                {"name": "Ironmongery", "children": ["handle", "bathroom lock", "B2B SS pull handle", "door stop"]},
                {"name": "Airbrick above door", "children": []},
            ]},
            "WALLS": {"order": 2, "items": [
                {"name": "smooth plaster", "children": []},
                {"name": "paint - orchid bay", "children": []},
                {"name": "Wall tiles", "children": ["tile trim", "grout dove grey", "chipped/broken/hollow tiles"]},
            ]},
            "WINDOWS": {"order": 3, "items": [
                {"name": "W3", "children": ["frame & coating", "glass", "hinges", "gaskets", "operation", "sill"]},
            ]},
            "FLOOR": {"order": 4, "items": [
                {"name": "Floor tile set out", "children": []},
                {"name": "chipped/broken/hollow tiles", "children": []},
                {"name": "grout dove grey", "children": []},
                {"name": "tile skirting", "children": []},
                {"name": "floor waste", "children": []},
            ]},
            "CEILING": {"order": 5, "items": [
                {"name": "paint - orchid bay", "children": []},
            ]},
            "ELECTRICAL": {"order": 6, "items": [
                {"name": "ceiling mounted light", "children": []},
                {"name": "shaver plug", "children": []},
                {"name": "light switch", "children": []},
                {"name": "extractor fan", "children": []},
            ]},
            "PLUMBING": {"order": 7, "items": [
                {"name": "Toilet", "children": ["pan", "seat", "cistern", "flush mechanism", "water connection", "silicone"]},
                {"name": "Basin", "children": ["basin", "mixer", "waste", "trap", "angel valves", "silicone"]},
                {"name": "Shower", "children": ["mixer", "arm & rose", "waste", "door/screen", "silicone", "control panel"]},
            ]},
            "JOINERY": {"order": 8, "items": [
                {"name": "Vanity", "children": ["carcass", "doors", "handles", "counter top"]},
                {"name": "Mirror", "children": []},
            ]},
            "FF&E": {"order": 9, "items": [
                {"name": "Toilet roll holder", "children": []},
                {"name": "Towel rail", "children": []},
                {"name": "Robe hook", "children": []},
            ]},
        }},
    }

    bedroom_cats = {
        "DOORS": {"order": 1, "items": [
            {"name": "Door leaf", "children": ["finished all round"]},
            {"name": "Frame", "children": ["hinges", "finish", "striker plate"]},
            {"name": "Ironmongery", "children": ["handle", "lockset", "door stop"]},
        ]},
        "WALLS": {"order": 2, "items": [
            {"name": "smooth plaster", "children": []},
            {"name": "paint - orchid bay", "children": []},
        ]},
        "WINDOWS": {"order": 3, "items": [
            {"name": "Window", "children": ["frame & coating", "glass", "hinges", "gaskets", "operation", "burglar bars", "sill"]},
        ]},
        "FLOOR": {"order": 4, "items": [
            {"name": "Floor tile set out", "children": []},
            {"name": "Soft joint cross", "children": []},
            {"name": "chipped/broken/hollow tiles", "children": []},
            {"name": "grout dove grey", "children": []},
            {"name": "tile skirting", "children": []},
        ]},
        "CEILING": {"order": 5, "items": [
            {"name": "paint - orchid bay", "children": []},
        ]},
        "ELECTRICAL": {"order": 6, "items": [
            {"name": "ceiling mounted light", "children": []},
            {"name": "double plug", "children": []},
            {"name": "bedside plug x2", "children": []},
            {"name": "light switch", "children": []},
            {"name": "USB charging point", "children": []},
        ]},
        "JOINERY": {"order": 7, "items": [
            {"name": "B.I.C.", "children": ["carcass", "doors", "handles", "shelves", "hanging rail", "door stop"]},
            {"name": "Study desk", "children": ["top", "finish", "edge"]},
        ]},
        "FF&E": {"order": 8, "items": [
            {"name": "Bed frame", "children": []},
            {"name": "Mattress", "children": []},
            {"name": "Desk chair", "children": []},
        ]},
    }

    for i, name in enumerate(['BEDROOM A', 'BEDROOM B', 'BEDROOM C', 'BEDROOM D'], start=4):
        template_data[name] = {"order": i, "categories": copy.deepcopy(bedroom_cats)}

    item_count = 0
    category_count = 0
    area_count = 0

    for area_name, area_data in template_data.items():
        area_id = gen_id()
        cur.execute("INSERT INTO area_template (id, tenant_id, area_name, area_order, unit_type) VALUES (?, ?, ?, ?, 'standard')",
            [area_id, tenant_id, area_name, area_data['order']])
        area_count += 1
        
        for cat_name, cat_data in area_data['categories'].items():
            cat_id = gen_id()
            cur.execute("INSERT INTO category_template (id, tenant_id, area_id, category_name, category_order) VALUES (?, ?, ?, ?, ?)",
                [cat_id, tenant_id, area_id, cat_name, cat_data['order']])
            category_count += 1
            
            item_order = 1
            for item in cat_data['items']:
                parent_id = gen_id()
                cur.execute("INSERT INTO item_template (id, tenant_id, category_id, item_description, item_order, parent_item_id) VALUES (?, ?, ?, ?, ?, NULL)",
                    [parent_id, tenant_id, cat_id, item['name'], item_order])
                item_count += 1
                item_order += 1
                
                for child_name in item['children']:
                    child_id = gen_id()
                    cur.execute("INSERT INTO item_template (id, tenant_id, category_id, item_description, item_order, parent_item_id) VALUES (?, ?, ?, ?, ?, ?)",
                        [child_id, tenant_id, cat_id, child_name, item_order, parent_id])
                    item_count += 1
                    item_order += 1

    conn.commit()
    print(f"\nTemplate loaded: {area_count} areas, {category_count} categories, {item_count} items")
    
    cur.execute("SELECT area_name FROM area_template ORDER BY area_order")
    print("Areas:", [r[0] for r in cur.fetchall()])
    conn.close()
    print("Done!")

if __name__ == '__main__':
    main()
