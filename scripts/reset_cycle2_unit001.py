"""Reset Cycle 2 inspection for Unit 001"""
import sqlite3
import os

db_path = os.environ.get('DATABASE_PATH', 'data/inspections.db')
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Find Unit 001
unit = cur.execute("SELECT id FROM unit WHERE unit_number = '001'").fetchone()
if not unit:
    print("Unit 001 not found")
    exit(1)

unit_id = unit['id']
print(f"Unit ID: {unit_id}")

# Find Cycle 2
cycle = cur.execute("""
    SELECT ic.id FROM inspection_cycle ic
    JOIN unit u ON ic.phase_id = u.phase_id
    WHERE u.id = ? AND ic.cycle_number = 2
""", [unit_id]).fetchone()

if not cycle:
    print("Cycle 2 not found")
    exit(1)

cycle_id = cycle['id']
print(f"Cycle 2 ID: {cycle_id}")

# Find inspection
inspection = cur.execute("""
    SELECT id FROM inspection WHERE unit_id = ? AND cycle_id = ?
""", [unit_id, cycle_id]).fetchone()

if inspection:
    inspection_id = inspection['id']
    print(f"Inspection ID: {inspection_id}")
    
    # Delete inspection items
    cur.execute("DELETE FROM inspection_item WHERE inspection_id = ?", [inspection_id])
    print("Deleted inspection items")
    
    # Delete inspection
    cur.execute("DELETE FROM inspection WHERE id = ?", [inspection_id])
    print("Deleted inspection")
    
    conn.commit()
    print("Cycle 2 inspection for Unit 001 reset successfully")
else:
    print("No Cycle 2 inspection found for Unit 001")

conn.close()
