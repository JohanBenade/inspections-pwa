"""
Patch inspect.html: Add back-to-reviews link + Mark Reviewed button for team_lead
Run from repo root: python3 patch_inspect.py
"""
import sys

filepath = 'app/templates/inspection/inspect.html'

with open(filepath, 'r') as f:
    content = f.read()

# Patch 1: Add "Back to My Reviews" link above the breadcrumb line
OLD_1 = '''                <div class="text-sm text-gray-500">
                    {{ inspection.project_name }} / {{ inspection.phase_name }}
                </div>'''

NEW_1 = '''                {% if current_user.role == 'team_lead' and inspection.status == 'submitted' %}
                <a href="{{ url_for('certification.my_reviews') }}" class="inline-block text-xs text-blue-600 hover:text-blue-800 mb-1">&larr; Back to My Reviews</a>
                {% endif %}
                <div class="text-sm text-gray-500">
                    {{ inspection.project_name }} / {{ inspection.phase_name }}
                </div>'''

if content.count(OLD_1) != 1:
    print(f"ERROR: Patch 1 pattern not found (or found multiple times)")
    sys.exit(1)
content = content.replace(OLD_1, NEW_1)
print("OK: Added Back to My Reviews link")

# Patch 2: Add Mark Reviewed button next to View PDF / Download
OLD_2 = '''                    <a href="{{ url_for('pdf.view_defects_html', unit_id=inspection.unit_id, cycle=inspection.cycle_id) }}" class="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded bg-gray-100 text-gray-700 hover:bg-gray-200" title="View defect list">View PDF</a>
                    <a href="{{ url_for('pdf.download_defects_pdf', unit_id=inspection.unit_id, cycle=inspection.cycle_id) }}" class="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded bg-gray-100 text-gray-700 hover:bg-gray-200" title="Download PDF">Download</a>
                    {% endif %}'''

NEW_2 = '''                    <a href="{{ url_for('pdf.view_defects_html', unit_id=inspection.unit_id, cycle=inspection.cycle_id) }}" class="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded bg-gray-100 text-gray-700 hover:bg-gray-200" title="View defect list">View PDF</a>
                    <a href="{{ url_for('pdf.download_defects_pdf', unit_id=inspection.unit_id, cycle=inspection.cycle_id) }}" class="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded bg-gray-100 text-gray-700 hover:bg-gray-200" title="Download PDF">Download</a>
                    {% endif %}
                    {% if current_user.role in ['team_lead', 'manager', 'admin'] and inspection.status == 'submitted' %}
                    <form method="POST" action="{{ url_for('certification.review_unit', unit_id=inspection.unit_id) }}" class="inline">
                        <button type="submit" class="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded bg-green-600 text-white hover:bg-green-700">Mark Reviewed</button>
                    </form>
                    {% endif %}'''

if content.count(OLD_2) != 1:
    print(f"ERROR: Patch 2 pattern not found (or found multiple times)")
    sys.exit(1)
content = content.replace(OLD_2, NEW_2)
print("OK: Added Mark Reviewed button")

with open(filepath, 'w') as f:
    f.write(content)

print("\nDone. Commit and push.")
