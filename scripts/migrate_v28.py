#!/usr/bin/env python3
"""
Migration script for v28
- Adds missing columns (safe if they already exist)
- Backfills defect.original_comment from defect_history

SAFE TO RUN MULTIPLE TIMES - does not delete any data
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'inspections.db')

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        print("Run setup_project.py first, or check your data folder.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("=== v28 Migration ===\n")
    
    # Step 1: Add missing columns (safe - skips if exists)
    print("Step 1: Adding missing columns...")
    columns_to_add = [
        ("defect", "original_comment", "TEXT"),
        ("defect", "clearance_note", "TEXT"),
        ("category_comment_history", "updated_by", "TEXT"),
    ]
    
    for table, column, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            print(f"  + Added {table}.{column}")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print(f"  - {table}.{column} already exists (OK)")
            else:
                print(f"  ! Error: {e}")
    
    conn.commit()
    
    # Step 2: Backfill original_comment from defect_history
    print("\nStep 2: Backfilling defect comments from history...")
    
    # Find defects with NULL original_comment
    defects = cursor.execute("""
        SELECT id FROM defect WHERE original_comment IS NULL OR original_comment = ''
    """).fetchall()
    
    updated = 0
    for defect in defects:
        # Get the FIRST (oldest) comment from history
        history = cursor.execute("""
            SELECT comment FROM defect_history 
            WHERE defect_id = ? 
            ORDER BY created_at ASC 
            LIMIT 1
        """, [defect['id']]).fetchone()
        
        if history and history['comment']:
            cursor.execute("""
                UPDATE defect SET original_comment = ? WHERE id = ?
            """, [history['comment'], defect['id']])
            updated += 1
    
    conn.commit()
    print(f"  + Updated {updated} defects with comments from history")
    
    # Step 3: Show summary
    print("\nStep 3: Summary...")
    
    total_defects = cursor.execute("SELECT COUNT(*) FROM defect").fetchone()[0]
    with_comments = cursor.execute(
        "SELECT COUNT(*) FROM defect WHERE original_comment IS NOT NULL AND original_comment != ''"
    ).fetchone()[0]
    
    print(f"  Total defects: {total_defects}")
    print(f"  With comments: {with_comments}")
    
    if total_defects > 0 and with_comments < total_defects:
        print(f"  Without comments: {total_defects - with_comments}")
        print("  (Some defects may have been created without comments)")
    
    conn.close()
    print("\n=== Migration Complete ===")

if __name__ == '__main__':
    migrate()
