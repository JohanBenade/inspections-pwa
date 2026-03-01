import sys

def replace_in_file(filepath, old, new, label):
    with open(filepath, 'r') as f:
        content = f.read()
    count = content.count(old)
    if count == 0:
        print(f"  FAIL: [{label}] old string not found in {filepath}")
        sys.exit(1)
    if count > 1:
        print(f"  FAIL: [{label}] old string found {count} times (expected 1)")
        sys.exit(1)
    content = content.replace(old, new)
    with open(filepath, 'w') as f:
        f.write(content)
    print(f"  OK: [{label}] {filepath}")

print("=== PDF notes: batch-aware fallback ===\n")

replace_in_file(
    'app/services/pdf_generator.py',
    """    # Process notes for PDF rendering (convert plain text to HTML if needed)
    general_notes_html = None
    exclusion_notes_html = None
    if cycle:
        gn = cycle['general_notes']
        if gn:
            general_notes_html = plain_text_to_html(gn)
        try:
            en = cycle['exclusion_notes']
            if en:
                exclusion_notes_html = plain_text_to_html(en)
        except (IndexError, KeyError):
            pass""",
    """    # Process notes for PDF rendering
    # If unit has a batch_unit record, use batch-level notes; otherwise cycle-level
    general_notes_html = None
    exclusion_notes_html = None

    batch_notes = None
    if cycle_id:
        batch_notes = query_db(\"\"\"
            SELECT ib.notes, ib.exclusion_notes
            FROM batch_unit bu
            JOIN inspection_batch ib ON bu.batch_id = ib.id
            WHERE bu.unit_id = ? AND bu.cycle_id = ? AND bu.status != 'removed'
            LIMIT 1
        \"\"\", [unit_id, cycle_id], one=True)

    if batch_notes:
        gn = batch_notes['notes']
        if gn:
            general_notes_html = plain_text_to_html(gn)
        en = batch_notes['exclusion_notes']
        if en:
            exclusion_notes_html = plain_text_to_html(en)
    elif cycle:
        gn = cycle['general_notes']
        if gn:
            general_notes_html = plain_text_to_html(gn)
        try:
            en = cycle['exclusion_notes']
            if en:
                exclusion_notes_html = plain_text_to_html(en)
        except (IndexError, KeyError):
            pass""",
    'pdf-batch-notes'
)

print("\n=== DONE ===")
print("Next: git add -A && git commit -m 'PDF: batch-level notes with cycle fallback' && git push")
