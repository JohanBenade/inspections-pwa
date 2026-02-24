"""
Patch: Context-aware back navigation (remaining patches)
Dashboard patch already applied. This handles:
1. Approvals review: add ?from=approvals to View links
2. certification.py: pass from= through redirect
3. inspect.html: context-aware back link

Run from repo root: python3 patch_back_nav2.py
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
# 1. Approvals review: add ?from=approvals to View links
# ============================================================
print("\n=== Patching review.html ===")

patch('app/templates/approvals/review.html',
    """<a href="{{ url_for('certification.view_unit', unit_id=unit.unit_id) }}"
                   class="text-xs text-blue-600 hover:text-blue-800 ml-2"
                   onclick="event.stopPropagation();">View &rarr;</a>""",
    """<a href="{{ url_for('certification.view_unit', unit_id=unit.unit_id, **{'from': 'approvals'}) }}"
                   class="text-xs text-blue-600 hover:text-blue-800 ml-2"
                   onclick="event.stopPropagation();">View &rarr;</a>""",
    "Added from=approvals to View links")

# ============================================================
# 2. certification.py: pass from= through redirect
# ============================================================
print("\n=== Patching certification.py ===")

patch('app/routes/certification.py',
    """        return redirect(url_for('inspection.inspect', inspection_id=inspection['id']))
    else:
        return redirect(url_for('inspection.start_inspection', unit_id=unit_id))""",
    """        back_from = request.args.get('from', '')
        target = url_for('inspection.inspect', inspection_id=inspection['id'])
        if back_from:
            target += '?from=' + back_from
        return redirect(target)
    else:
        return redirect(url_for('inspection.start_inspection', unit_id=unit_id))""",
    "Pass from= parameter through view_unit redirect")

# ============================================================
# 3. inspect.html: context-aware back navigation
# ============================================================
print("\n=== Patching inspect.html ===")

patch('app/templates/inspection/inspect.html',
    """                {% if current_user.role == 'team_lead' and inspection.status == 'submitted' %}
                <a href="{{ url_for('certification.my_reviews') }}" class="inline-block text-xs text-blue-600 hover:text-blue-800 mb-1">&larr; Back to My Reviews</a>
                {% elif current_user.role in ['manager', 'admin'] %}
                <a href="{{ url_for('approvals.pipeline') }}" class="inline-block text-xs text-blue-600 hover:text-blue-800 mb-1">&larr; Back to Approvals</a>
                {% endif %}""",
    """                {% set back_from = request.args.get('from', '') %}
                {% if back_from == 'analytics' %}
                <a href="{{ url_for('analytics.dashboard') }}" class="inline-block text-xs text-blue-600 hover:text-blue-800 mb-1">&larr; Back to Analytics</a>
                {% elif back_from == 'approvals' %}
                <a href="{{ url_for('approvals.pipeline') }}" class="inline-block text-xs text-blue-600 hover:text-blue-800 mb-1">&larr; Back to Approvals</a>
                {% elif current_user.role == 'team_lead' and inspection.status == 'submitted' %}
                <a href="{{ url_for('certification.my_reviews') }}" class="inline-block text-xs text-blue-600 hover:text-blue-800 mb-1">&larr; Back to My Reviews</a>
                {% elif current_user.role in ['manager', 'admin'] %}
                <a href="{{ url_for('approvals.pipeline') }}" class="inline-block text-xs text-blue-600 hover:text-blue-800 mb-1">&larr; Back to Approvals</a>
                {% endif %}""",
    "Context-aware back navigation based on from= param")

print("\nDone. Commit and push.")
