#!/usr/bin/env python3
"""
Clear all inspections, inspection items, and defects for retesting.
Run from inspections-pwa directory: python3 scripts/reset_inspections.py
"""

def main():
    import sqlite3
    conn = sqlite3.connect('data/inspections.db')
    cur = conn.cursor()
    
    # Count before
    inspections = cur.execute("SELECT COUNT(*) FROM inspection").fetchone()[0]
    items = cur.execute("SELECT COUNT(*) FROM inspection_item").fetchone()[0]
    defects = cur.execute("SELECT COUNT(*) FROM defect").fetchone()[0]
    
    print(f"Before: {inspections} inspections, {items} items, {defects} defects")
    
    # Delete in order (foreign key safe)
    cur.execute("DELETE FROM defect")
    cur.execute("DELETE FROM inspection_item")
    cur.execute("DELETE FROM inspection")
    
    conn.commit()
    conn.close()
    
    print(f"CLEARED: All inspections, items, and defects removed")
    print(f"Ready for fresh testing")

if __name__ == '__main__':
    main()
