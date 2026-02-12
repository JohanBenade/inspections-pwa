"""
Defect description wash utility.
Two-tier fuzzy matching against defect_library:
  1. Item-specific entries (matching item_template_id)
  2. Category fallback entries (matching category_name, no item_template_id)
  3. No match: clean raw text + add to library
Threshold: 0.7 (proven on 849 defects across 26 units)
"""
from difflib import SequenceMatcher
from app.utils import generate_id
from app.services.db import query_db


WASH_THRESHOLD = 0.7


def _fuzzy_match(text, candidates, threshold=WASH_THRESHOLD):
    """Find best match from candidates. Returns (match_text, score) or (None, 0)."""
    best_match = None
    best_score = 0
    text_lower = text.lower().strip()
    for candidate in candidates:
        score = SequenceMatcher(None, text_lower, candidate.lower().strip()).ratio()
        if score > best_score:
            best_score = score
            best_match = candidate
    if best_score >= threshold:
        return best_match, best_score
    return None, 0


def wash_description(db, tenant_id, item_template_id, raw_desc):
    """
    Wash a defect description against the defect library.
    Returns the washed description (library match or cleaned raw text).
    Side effects: creates library entry if no match, increments usage_count on match.
    """
    if not raw_desc or not raw_desc.strip():
        return raw_desc

    # Get category name for this template
    cat_row = query_db("""
        SELECT ct.category_name
        FROM item_template it
        JOIN category_template ct ON it.category_id = ct.id
        WHERE it.id = ?
    """, [item_template_id], one=True)
    cat_name = cat_row['category_name'] if cat_row else 'UNKNOWN'

    # Tier 1: Item-specific matches
    item_entries = query_db("""
        SELECT description FROM defect_library
        WHERE tenant_id = ? AND item_template_id = ?
        ORDER BY usage_count DESC
    """, [tenant_id, item_template_id])

    if item_entries:
        candidates = [r['description'] for r in item_entries]
        match, score = _fuzzy_match(raw_desc, candidates)
        if match:
            db.execute("""
                UPDATE defect_library SET usage_count = usage_count + 1
                WHERE tenant_id = ? AND item_template_id = ? AND description = ?
            """, [tenant_id, item_template_id, match])
            return match

    # Tier 2: Category fallback
    cat_entries = query_db("""
        SELECT description FROM defect_library
        WHERE tenant_id = ? AND category_name = ? AND item_template_id IS NULL
        ORDER BY usage_count DESC
    """, [tenant_id, cat_name])

    if cat_entries:
        candidates = [r['description'] for r in cat_entries]
        match, score = _fuzzy_match(raw_desc, candidates)
        if match:
            db.execute("""
                UPDATE defect_library SET usage_count = usage_count + 1
                WHERE tenant_id = ? AND category_name = ? AND item_template_id IS NULL AND description = ?
            """, [tenant_id, cat_name, match])
            return match

    # Tier 3: No match - clean up and add to library
    cleaned = raw_desc.strip()
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]

    db.execute("""
        INSERT INTO defect_library
        (id, tenant_id, category_name, item_template_id, description,
         usage_count, is_system, created_at)
        VALUES (?, ?, ?, ?, ?, 1, 0, CURRENT_TIMESTAMP)
    """, [generate_id(), tenant_id, cat_name, item_template_id, cleaned])

    return cleaned
