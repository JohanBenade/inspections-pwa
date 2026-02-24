"""
Patch: Approvals improvements
1. Fix None-None bug (unit_start/unit_end) in approvals.py
2. Make unit rows clickable in review.html (View link)
3. Add back navigation on inspect page for manager/admin

Run from repo root: python3 patch_approvals.py
"""
import sys

def patch(filepath, old, new, desc):
    with open(filepath, 'r') as f:
        content = f.read()
    count = content.count(old)
    if count == 0:
        print(f"  ERROR: Pattern not found in {filepath}: {desc}")
        print(f"  Looking for: {old[:100]}...")
        sys.exit(1)
    if count > 1:
        print(f"  ERROR: Pattern found {count} times in {filepath}: {desc}")
        sys.exit(1)
    content = content.replace(old, new)
    with open(filepath, 'w') as f:
        f.write(content)
    print(f"  OK: {desc}")

# ============================================================
# 1. Fix None-None in approvals.py - add unit_start/unit_end to cycle
# ============================================================
print("\n=== Patching approvals.py ===")

patch('app/routes/approvals.py',
    """    if not inspections:
        return {'cycle': cycle, 'units': [], 'stats': {
            'total': 0, 'reviewed': 0, 'defects': 0, 'to_fix': 0}}""",
    """    # Compute unit range for display
    unit_numbers = sorted([insp['unit_number'] for insp in inspections])
    cycle['unit_start'] = unit_numbers[0] if unit_numbers else ''
    cycle['unit_end'] = unit_numbers[-1] if unit_numbers else ''

    if not inspections:
        return {'cycle': cycle, 'units': [], 'stats': {
            'total': 0, 'reviewed': 0, 'defects': 0, 'to_fix': 0}}""",
    "Added unit_start/unit_end computation")

# Wait - the unit_numbers calc is BEFORE the empty check, but inspections
# is already populated by this point. Actually the empty check is redundant
# if we already have inspections. But the unit_start/end calc needs to be
# AFTER inspections is populated. Let me check... yes, inspections is fetched
# on lines 148-156, and the empty check is at line 158. So placing the
# computation before the empty check but after the fetch is correct.
# Actually wait - if inspections is empty, unit_numbers will be empty too,
# and we set '' for both. Then the empty check returns. That's fine.

# ============================================================
# 2. Make unit rows clickable in review.html - add View link
# ============================================================
print("\n=== Patching review.html ===")

patch('app/templates/approvals/review.html',
    """                <span class="font-semibold text-gray-900">Unit {{ unit.unit_number }}</span>
                <span class="text-sm text-gray-400 ml-2">{{ unit.defect_count }} defects</span>""",
    """                <span class="font-semibold text-gray-900">Unit {{ unit.unit_number }}</span>
                <span class="text-sm text-gray-400 ml-2">{{ unit.defect_count }} defects</span>
                <a href="{{ url_for('certification.view_unit', unit_id=unit.unit_id) }}"
                   class="text-xs text-blue-600 hover:text-blue-800 ml-2"
                   onclick="event.stopPropagation();">View &rarr;</a>""",
    "Added View link on unit rows")

# ============================================================
# 3. Update inspect.html back navigation for manager/admin
# ============================================================
print("\n=== Patching inspect.html ===")

patch('app/templates/inspection/inspect.html',
    """                {% if current_user.role == 'team_lead' and inspection.status == 'submitted' %}
                <a href="{{ url_for('certification.my_reviews') }}" class="inline-block text-xs text-blue-600 hover:text-blue-800 mb-1">&larr; Back to My Reviews</a>
                {% endif %}""",
    """                {% if current_user.role == 'team_lead' and inspection.status == 'submitted' %}
                <a href="{{ url_for('certification.my_reviews') }}" class="inline-block text-xs text-blue-600 hover:text-blue-800 mb-1">&larr; Back to My Reviews</a>
                {% elif current_user.role in ['manager', 'admin'] %}
                <a href="{{ url_for('approvals.pipeline') }}" class="inline-block text-xs text-blue-600 hover:text-blue-800 mb-1">&larr; Back to Approvals</a>
                {% endif %}""",
    "Added Back to Approvals for manager/admin")

print("\nDone. Commit and push.")
