"""
Defect description cleaner.
Strips whitespace and capitalises first character.
No fuzzy matching, no library lookup.
"""


def wash_description(db, tenant_id, item_template_id, raw_desc):
    """
    Clean a defect description: strip whitespace, capitalise first char.
    Returns cleaned text. No DB interaction.

    Signature kept for call-site compatibility; db, tenant_id,
    item_template_id are unused.
    """
    if not raw_desc or not raw_desc.strip():
        return raw_desc
    cleaned = raw_desc.strip()
    return cleaned[0].upper() + cleaned[1:]
