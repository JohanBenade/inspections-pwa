"""
Create and seed defect_library table.
Run on Render console: python3 scripts/create_defect_library.py
"""
import sqlite3
import uuid

def generate_id():
    return uuid.uuid4().hex[:8]

conn = sqlite3.connect('/var/data/inspections.db')
cur = conn.cursor()

print("=== CREATING DEFECT LIBRARY ===\n")

# 1. Create table
cur.execute("""
CREATE TABLE IF NOT EXISTS defect_library (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    category_name TEXT NOT NULL,
    item_template_id TEXT,
    description TEXT NOT NULL,
    usage_count INTEGER DEFAULT 0,
    is_system INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Create index for fast lookups
cur.execute("""
CREATE INDEX IF NOT EXISTS idx_defect_library_lookup 
ON defect_library(tenant_id, category_name, item_template_id)
""")

conn.commit()
print("Table created.\n")

# 2. Clear existing entries (for re-runs)
cur.execute("DELETE FROM defect_library WHERE tenant_id = 'MONOGRAPH'")
print(f"Cleared existing entries.\n")

# 3. Extract item-specific mappings from Cycle 1 defects
print("Seeding from Cycle 1 data...")
cur.execute("""
    SELECT it.id, ct.category_name, d.original_comment, COUNT(*) as cnt
    FROM defect d
    JOIN item_template it ON d.item_template_id = it.id
    JOIN category_template ct ON it.category_id = ct.id
    WHERE d.tenant_id = 'MONOGRAPH'
    GROUP BY it.id, ct.category_name, d.original_comment
    ORDER BY cnt DESC
""")

item_specific = 0
for row in cur.fetchall():
    item_id, category, description, count = row
    lib_id = generate_id()
    cur.execute("""
        INSERT INTO defect_library (id, tenant_id, category_name, item_template_id, description, usage_count, is_system)
        VALUES (?, 'MONOGRAPH', ?, ?, ?, ?, 0)
    """, [lib_id, category, item_id, description, count])
    item_specific += 1

print(f"  Item-specific entries: {item_specific}")

# 4. Add category-level fallbacks (industry standard defects)
category_fallbacks = {
    'WINDOWS': [
        'Window does not lock',
        'Handle broken/damaged',
        'Cracked glass',
        'Weatherstrip damaged',
        'Hinges stiff',
    ],
    'DOORS': [
        'Door does not close properly',
        'Door warped',
        'Gap under door incorrect',
        'Hinge screws loose',
        'Key does not work',
        'Closer not functioning',
    ],
    'PLUMBING': [
        'Tap dripping/leaking',
        'Drain blocked/slow',
        'Toilet runs continuously',
        'No hot water',
        'Basin not sealed to wall',
        'Shower head loose',
    ],
    'ELECTRICAL': [
        'Socket not working',
        'Light not working',
        'Switch loose in wall',
        'Exposed wiring',
        'Earth leakage tripping',
    ],
    'FLOOR': [
        'Tile loose',
        'Uneven surface',
        'Skirting loose',
        'Vinyl lifting',
        'Grout cracked',
    ],
    'WALLS': [
        'Crack in wall',
        'Damp/moisture visible',
        'Paint bubbling',
        'Hole in wall',
        'Plaster damaged',
    ],
    'CEILING': [
        'Crack in ceiling',
        'Water stain visible',
        'Paint peeling',
        'Sagging/uneven',
    ],
    'JOINERY': [
        'Door does not close',
        'Drawer stuck',
        'Handle loose',
        'Shelf sagging',
        'Hinge broken',
    ],
}

fallback_count = 0
for category, defects in category_fallbacks.items():
    for desc in defects:
        # Check if this exact description already exists for the category
        cur.execute("""
            SELECT id FROM defect_library 
            WHERE tenant_id = 'MONOGRAPH' AND category_name = ? AND description = ? AND item_template_id IS NULL
        """, [category, desc])
        if not cur.fetchone():
            lib_id = generate_id()
            cur.execute("""
                INSERT INTO defect_library (id, tenant_id, category_name, item_template_id, description, usage_count, is_system)
                VALUES (?, 'MONOGRAPH', ?, NULL, ?, 0, 1)
            """, [lib_id, category, desc])
            fallback_count += 1

print(f"  Category fallbacks: {fallback_count}")

conn.commit()

# 5. Summary
cur.execute("SELECT COUNT(*) FROM defect_library WHERE tenant_id = 'MONOGRAPH'")
total = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM defect_library WHERE tenant_id = 'MONOGRAPH' AND item_template_id IS NOT NULL")
item_level = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM defect_library WHERE tenant_id = 'MONOGRAPH' AND item_template_id IS NULL")
category_level = cur.fetchone()[0]

print(f"\n=== SUMMARY ===")
print(f"Total entries:     {total}")
print(f"Item-specific:     {item_level}")
print(f"Category fallback: {category_level}")

# Show top items by suggestion count
print(f"\n=== TOP ITEMS BY SUGGESTIONS ===")
cur.execute("""
    SELECT it.item_description, COUNT(*) as suggestions, SUM(dl.usage_count) as total_usage
    FROM defect_library dl
    JOIN item_template it ON dl.item_template_id = it.id
    WHERE dl.tenant_id = 'MONOGRAPH'
    GROUP BY it.item_description
    ORDER BY suggestions DESC
    LIMIT 10
""")
for row in cur.fetchall():
    print(f"  {row[1]:2} suggestions | {row[2]:3} uses | {row[0]}")

conn.close()
print("\nDONE")
