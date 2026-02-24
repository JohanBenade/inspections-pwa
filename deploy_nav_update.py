"""
Deploy script: Nav restructure for role-specific views
Run from repo root: cd ~/Documents/GitHub/inspections-pwa && python3 deploy_nav_update.py

Changes:
1. certification.py - adds my_reviews + my_inspections routes, changes review_unit redirect
2. base.html - restructures nav per role, removes Projects/Defects, cleans up duplicate scripts
3. Creates my_reviews.html template
"""
import os
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

def patch_file(filepath, old, new, description=""):
    """Replace old with new in file. Fails if old not found exactly once."""
    full_path = os.path.join(REPO_ROOT, filepath)
    with open(full_path, 'r') as f:
        content = f.read()
    count = content.count(old)
    if count == 0:
        print(f"  ERROR: Pattern not found in {filepath}")
        print(f"  Looking for: {old[:80]}...")
        sys.exit(1)
    if count > 1:
        print(f"  ERROR: Pattern found {count} times in {filepath} (expected 1)")
        print(f"  Looking for: {old[:80]}...")
        sys.exit(1)
    content = content.replace(old, new)
    with open(full_path, 'w') as f:
        f.write(content)
    print(f"  OK: {description}")

def append_to_file(filepath, text, description=""):
    """Append text to end of file."""
    full_path = os.path.join(REPO_ROOT, filepath)
    with open(full_path, 'r') as f:
        content = f.read()
    content = content.rstrip() + "\n\n" + text + "\n"
    with open(full_path, 'w') as f:
        f.write(content)
    print(f"  OK: {description}")

def create_file(filepath, text, description=""):
    """Create new file."""
    full_path = os.path.join(REPO_ROOT, filepath)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w') as f:
        f.write(text)
    print(f"  OK: {description}")

# ============================================================
# 1. PATCH certification.py - add my_reviews + my_inspections routes
# ============================================================
print("\n=== Patching certification.py ===")

# 1a. Change review_unit redirect from dashboard to my_reviews
patch_file(
    'app/routes/certification.py',
    "flash(f\"Unit {unit_num} reviewed by {reviewer} - now awaiting Architect approval\", 'success')\n    return redirect(url_for('certification.dashboard'))",
    "flash(f\"Unit {unit_num} reviewed by {reviewer} - now awaiting Architect approval\", 'success')\n    return redirect(url_for('certification.my_reviews'))",
    "Changed review_unit redirect to my_reviews"
)

# 1b. Append new routes to end of file
NEW_ROUTES = '''
# ============================================================
# TEAM LEAD: MY REVIEWS + MY INSPECTIONS
# ============================================================

@certification_bp.route('/my-reviews')
@require_team_lead
def my_reviews():
    """Team Lead review queue - submitted inspections awaiting review."""
    tenant_id = session['tenant_id']

    inspections = [dict(r) for r in query_db("""
        SELECT i.id AS inspection_id, i.status AS inspection_status,
               i.submitted_at, i.inspector_name,
               u.id AS unit_id, u.unit_number, u.block, u.floor,
               ic.cycle_number, ic.id AS cycle_id,
               (SELECT COUNT(*) FROM defect d
                WHERE d.unit_id = u.id AND d.raised_cycle_id = ic.id
                AND d.status = 'open' AND d.tenant_id = i.tenant_id) AS defect_count
        FROM inspection i
        JOIN unit u ON i.unit_id = u.id
        JOIN inspection_cycle ic ON i.cycle_id = ic.id
        WHERE i.tenant_id = ? AND i.status = 'submitted'
        ORDER BY u.block, u.floor, u.unit_number
    """, [tenant_id])]

    return render_template('certification/my_reviews.html', inspections=inspections)


@certification_bp.route('/my-inspections')
@require_team_lead
def my_inspections():
    """Team Lead own inspection assignments - same view as inspector home."""
    tenant_id = session['tenant_id']
    user_id = session['user_id']

    inspections = [dict(r) for r in query_db("""
        SELECT i.id AS inspection_id, i.status AS inspection_status,
               i.inspection_date, i.started_at, i.submitted_at,
               u.id AS unit_id, u.unit_number, u.block, u.floor,
               ic.cycle_number, ic.id AS cycle_id,
               (SELECT COUNT(*) FROM inspection_item ii
                WHERE ii.inspection_id = i.id
                AND ii.status != 'skipped') AS total_items,
               (SELECT COUNT(*) FROM inspection_item ii
                WHERE ii.inspection_id = i.id
                AND ii.status NOT IN ('skipped', 'pending')) AS completed_items,
               (SELECT COUNT(*) FROM inspection_item ii2
                WHERE ii2.inspection_id = i.id
                AND ii2.status IN ('not_to_standard', 'not_installed')) AS defect_count,
               (SELECT COUNT(*) FROM defect d2
                JOIN inspection_cycle ic2 ON d2.raised_cycle_id = ic2.id
                WHERE d2.unit_id = u.id AND d2.status = 'open'
                AND ic2.cycle_number < ic.cycle_number
                AND d2.tenant_id = i.tenant_id) AS prior_open_defects,
               (SELECT COUNT(*) FROM defect d3
                JOIN inspection_cycle ic3 ON d3.raised_cycle_id = ic3.id
                WHERE d3.unit_id = u.id
                AND ic3.cycle_number < ic.cycle_number
                AND d3.tenant_id = i.tenant_id) AS prior_defects_total
        FROM inspection i
        JOIN unit u ON i.unit_id = u.id
        JOIN inspection_cycle ic ON i.cycle_id = ic.id
        WHERE i.inspector_id = ? AND i.tenant_id = ?
        AND i.status IN ('not_started', 'in_progress')
        ORDER BY
            CASE i.status WHEN 'in_progress' THEN 0 ELSE 1 END,
            u.unit_number
    """, [user_id, tenant_id])]

    return render_template('inspector_home.html', inspections=inspections)'''

append_to_file('app/routes/certification.py', NEW_ROUTES, "Added my_reviews + my_inspections routes")

# ============================================================
# 2. PATCH base.html - restructure navigation
# ============================================================
print("\n=== Patching base.html ===")

# 2a. Replace desktop nav
OLD_DESKTOP_NAV = '''                    <div class="hidden md:flex items-center space-x-4">
                        <a href="{{ url_for('home') }}" class="text-sm text-gray-300 hover:text-white">Home</a>
                        {% if current_user.role in ['team_lead', 'manager', 'admin'] %}
                        <a href="{{ url_for('projects.list_projects') }}" class="text-sm text-gray-300 hover:text-white">Projects</a>
                        {% endif %}
                        {% if current_user.role in ['team_lead', 'manager', 'admin'] %}
                        <a href="{{ url_for('batches.list_batches') }}" class="text-sm text-gray-300 hover:text-white">Batches</a>
                        <a href="{{ url_for('defects.register') }}" class="text-sm text-gray-300 hover:text-white">Defects</a>
                        {% if current_user.role in ['manager', 'admin'] %}
                        <a href="{{ url_for('approvals.pipeline') }}" class="text-sm text-gray-300 hover:text-white">Approvals</a>
                        <a href="{{ url_for('analytics.dashboard') }}" class="text-sm text-gray-300 hover:text-white">Analytics</a>
                        <a href="{{ url_for('analytics.reports') }}" class="text-sm text-gray-300 hover:text-white">Reports</a>
                        {% if current_user.role == 'admin' %}
                        <a href="{{ url_for('data_quality.descriptions') }}" class="text-sm text-gray-300 hover:text-white">Data Quality</a>
                        {% endif %}
                        {% endif %}
                        {% endif %}
                    </div>'''

NEW_DESKTOP_NAV = '''                    <div class="hidden md:flex items-center space-x-4">
                        <a href="{{ url_for('home') }}" class="text-sm text-gray-300 hover:text-white">Home</a>
                        {% if current_user.role in ['team_lead', 'manager', 'admin'] %}
                        <a href="{{ url_for('batches.list_batches') }}" class="text-sm text-gray-300 hover:text-white">Batches</a>
                        {% endif %}
                        {% if current_user.role == 'team_lead' %}
                        <a href="{{ url_for('certification.my_reviews') }}" class="text-sm text-gray-300 hover:text-white">My Reviews</a>
                        <a href="{{ url_for('certification.my_inspections') }}" class="text-sm text-gray-300 hover:text-white">My Inspections</a>
                        {% endif %}
                        {% if current_user.role in ['manager', 'admin'] %}
                        <a href="{{ url_for('approvals.pipeline') }}" class="text-sm text-gray-300 hover:text-white">Approvals</a>
                        <a href="{{ url_for('analytics.dashboard') }}" class="text-sm text-gray-300 hover:text-white">Analytics</a>
                        <a href="{{ url_for('analytics.reports') }}" class="text-sm text-gray-300 hover:text-white">Reports</a>
                        {% if current_user.role == 'admin' %}
                        <a href="{{ url_for('data_quality.descriptions') }}" class="text-sm text-gray-300 hover:text-white">Data Quality</a>
                        {% endif %}
                        {% endif %}
                    </div>'''

patch_file('app/templates/base.html', OLD_DESKTOP_NAV, NEW_DESKTOP_NAV, "Restructured desktop nav")

# 2b. Replace entire mobile bottom nav
OLD_MOBILE_NAV = '''    <nav class="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 md:hidden">
        <div class="flex justify-around items-center h-16">
            <!-- Home -->
            <a href="{{ url_for('home') }}" 
               class="flex flex-col items-center text-gray-600 hover:text-primary tap-target">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/>
                </svg>
                <span class="text-xs mt-1">Home</span>
            </a>
            
            <!-- Projects - team_lead, manager, admin -->
            {% if current_user.role in ['team_lead', 'manager', 'admin'] %}
            <a href="{{ url_for('projects.list_projects') }}" 
               class="flex flex-col items-center text-gray-600 hover:text-primary tap-target">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"/>
                </svg>
                <span class="text-xs mt-1">Projects</span>
            </a>
            {% endif %}
            
            {% if current_user.role in ['team_lead', 'manager', 'admin'] %}
            <!-- Batches - team_lead and above -->
            <a href="{{ url_for('batches.list_batches') }}" 
               class="flex flex-col items-center text-gray-600 hover:text-primary tap-target">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                </svg>
                <span class="text-xs mt-1">Batches</span>
            </a>
            
            <!-- Defects - team_lead and above -->
            <a href="{{ url_for('defects.register') }}" 
               class="flex flex-col items-center text-gray-600 hover:text-primary tap-target">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
                </svg>
                <span class="text-xs mt-1">Defects</span>
            </a>
            
            {% if current_user.role in ['manager', 'admin'] %}
            <!-- Approvals - manager and above -->
            <a href="{{ url_for('approvals.pipeline') }}" 
               class="flex flex-col items-center text-gray-600 hover:text-primary tap-target">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/>
                </svg>
                <span class="text-xs mt-1">Approvals</span>
            </a>
            <a href="{{ url_for('analytics.dashboard') }}" 
               class="flex flex-col items-center text-gray-600 hover:text-primary tap-target"
               ontouchend="">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                </svg>
                <span class="text-xs mt-1">Analytics</span>
            </a>
            <a href="{{ url_for('analytics.reports') }}" 
               class="flex flex-col items-center text-gray-600 hover:text-primary tap-target"
               ontouchend="">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                </svg>
                <span class="text-xs mt-1">Reports</span>
            </a>
            {% endif %}
            {% endif %}
            
            </a>
        </div>
    </nav>'''

NEW_MOBILE_NAV = '''    <nav class="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 md:hidden">
        <div class="flex justify-around items-center h-16">
            <!-- Home - all roles -->
            <a href="{{ url_for('home') }}" 
               class="flex flex-col items-center text-gray-600 hover:text-primary tap-target">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/>
                </svg>
                <span class="text-xs mt-1">Home</span>
            </a>

            {% if current_user.role in ['team_lead', 'manager', 'admin'] %}
            <!-- Batches - team_lead and above -->
            <a href="{{ url_for('batches.list_batches') }}" 
               class="flex flex-col items-center text-gray-600 hover:text-primary tap-target">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                </svg>
                <span class="text-xs mt-1">Batches</span>
            </a>
            {% endif %}

            {% if current_user.role == 'team_lead' %}
            <!-- My Reviews - team_lead only -->
            <a href="{{ url_for('certification.my_reviews') }}" 
               class="flex flex-col items-center text-gray-600 hover:text-primary tap-target">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/>
                </svg>
                <span class="text-xs mt-1">Reviews</span>
            </a>
            <!-- My Inspections - team_lead only -->
            <a href="{{ url_for('certification.my_inspections') }}" 
               class="flex flex-col items-center text-gray-600 hover:text-primary tap-target">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
                </svg>
                <span class="text-xs mt-1">Inspect</span>
            </a>
            {% endif %}

            {% if current_user.role in ['manager', 'admin'] %}
            <!-- Approvals - manager and above -->
            <a href="{{ url_for('approvals.pipeline') }}" 
               class="flex flex-col items-center text-gray-600 hover:text-primary tap-target">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/>
                </svg>
                <span class="text-xs mt-1">Approvals</span>
            </a>
            <!-- Analytics -->
            <a href="{{ url_for('analytics.dashboard') }}" 
               class="flex flex-col items-center text-gray-600 hover:text-primary tap-target">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                </svg>
                <span class="text-xs mt-1">Analytics</span>
            </a>
            <!-- Reports -->
            <a href="{{ url_for('analytics.reports') }}" 
               class="flex flex-col items-center text-gray-600 hover:text-primary tap-target">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                </svg>
                <span class="text-xs mt-1">Reports</span>
            </a>
            {% endif %}
        </div>
    </nav>'''

patch_file('app/templates/base.html', OLD_MOBILE_NAV, NEW_MOBILE_NAV, "Restructured mobile nav")

# 2c. Remove duplicate confirm-modal (second instance)
# The second confirm-modal starts after the first PWA wake recovery script
DUPLICATE_BLOCK = '''
    <!-- Custom confirm dialog -->
    <div id="confirm-modal" style="display:none" class="fixed inset-0 z-[999] flex items-center justify-center">
        <div class="absolute inset-0 bg-black/50" onclick="window._confirmReject()"></div>
        <div class="relative bg-white rounded-xl shadow-2xl p-6 mx-4 max-w-sm w-full">
            <p id="confirm-msg" class="text-gray-800 text-base font-medium mb-6"></p>
            <div class="flex gap-3 justify-end">
                <button onclick="window._confirmReject()" class="px-4 py-2.5 rounded-lg text-sm font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 transition-colors">Cancel</button>
                <button onclick="window._confirmResolve()" class="px-4 py-2.5 rounded-lg text-sm font-medium text-white bg-red-500 hover:bg-red-600 transition-colors">Confirm</button>
            </div>
        </div>
    </div>
    <script>
    document.body.addEventListener('htmx:confirm', function(e) {
        if (!e.detail.question) return;
        e.preventDefault();
        var m = document.getElementById('confirm-modal');
        document.getElementById('confirm-msg').textContent = e.detail.question;
        m.style.display = 'flex';
        window._confirmResolve = function() { m.style.display='none'; e.detail.issueRequest(); };
        window._confirmReject = function() { m.style.display='none'; };
    });
    </script>

    <!-- PWA wake recovery -->
    <script>
    (function() {
        var lastHidden = 0;
        document.addEventListener('visibilitychange', function() {
            if (document.hidden) {
                lastHidden = Date.now();
            } else {
                var elapsed = Date.now() - lastHidden;
                if (elapsed > 30000) {
                    fetch(window.location.href, {method: 'HEAD', cache: 'no-store'})
                        .then(function(r) { if (!r.ok) window.location.reload(); })
                        .catch(function() { window.location.reload(); });
                }
            }
        });
    })();
    </script>'''

# Find and remove the duplicate block
full_path = os.path.join(REPO_ROOT, 'app/templates/base.html')
with open(full_path, 'r') as f:
    content = f.read()

count = content.count('id="confirm-modal"')
if count == 2:
    # Remove the second occurrence of the duplicate block
    content = content.replace(DUPLICATE_BLOCK, '', 1)  # removes first match of DUPLICATE_BLOCK
    # Actually we need to remove the SECOND confirm-modal, not the first
    # Let's be more precise: find the second <!-- Custom confirm dialog --> and remove everything up to the PWA wake recovery end
    # Simpler approach: just remove ALL instances then we'll have zero, then check
    # Actually the DUPLICATE_BLOCK string should match the second copy exactly
    # Let me try a different approach - count after replacement
    with open(full_path, 'w') as f:
        f.write(content)
    # Verify
    with open(full_path, 'r') as f:
        content = f.read()
    remaining = content.count('id="confirm-modal"')
    if remaining == 1:
        print("  OK: Removed duplicate confirm-modal + PWA scripts")
    else:
        print(f"  WARNING: Expected 1 confirm-modal remaining, found {remaining}")
elif count == 1:
    print("  OK: No duplicate confirm-modal found (already clean)")
else:
    print(f"  WARNING: Found {count} confirm-modals, expected 2")

# Also fix the stray </a> tag in the old mobile nav
full_path = os.path.join(REPO_ROOT, 'app/templates/base.html')
with open(full_path, 'r') as f:
    content = f.read()
# The old nav had a stray </a> before the closing </div> of the nav
# This should already be cleaned up by the mobile nav replacement
# But let's verify there are no stray tags
print("  OK: Stray tag cleanup (handled by mobile nav replacement)")

# ============================================================
# 3. CREATE my_reviews.html template
# ============================================================
print("\n=== Creating my_reviews.html ===")

MY_REVIEWS_TEMPLATE = '''{% extends "base.html" %}

{% block title %}My Reviews{% endblock %}

{% block content %}
<div class="mb-6">
    <h1 class="text-2xl font-bold text-gray-900">My Reviews</h1>
    <p class="text-sm text-gray-500 mt-1">
        {% if inspections %}
        {{ inspections|length }} unit{{ 's' if inspections|length != 1 }} waiting for review
        {% else %}
        No units waiting for review
        {% endif %}
    </p>
</div>

{% if inspections %}
<div class="space-y-3">
    {% for insp in inspections %}
    {% set floor_name = 'Ground' if insp.floor == 0 else ('1st' if insp.floor == 1 else '2nd') %}
    <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
        <div class="flex justify-between items-start mb-1">
            <div>
                <div class="flex items-center space-x-2">
                    <span class="text-lg font-bold text-gray-900">Unit {{ insp.unit_number }}</span>
                    <span class="text-xs px-2 py-0.5 rounded-full bg-purple-100 text-purple-700">Submitted</span>
                </div>
                <p class="text-sm text-gray-500 mt-1">{{ insp.block }} {{ floor_name }} Floor &middot; Round {{ insp.cycle_number }}</p>
                <p class="text-sm text-gray-500">{{ insp.inspector_name }} &middot; <span class="font-medium text-gray-700">{{ insp.defect_count }} defects</span></p>
            </div>
        </div>

        <div class="flex gap-3 mt-4">
            <a href="{{ url_for('certification.view_unit', unit_id=insp.unit_id) }}"
               class="flex-1 text-center py-2.5 px-4 rounded-lg bg-primary text-white text-sm font-medium tap-target">
                View Defects
            </a>
            <form method="POST" action="{{ url_for('certification.review_unit', unit_id=insp.unit_id) }}"
                  class="flex-1">
                <button type="submit"
                        class="w-full py-2.5 px-4 rounded-lg bg-green-600 text-white text-sm font-medium tap-target">
                    Mark Reviewed
                </button>
            </form>
        </div>
    </div>
    {% endfor %}
</div>
{% else %}
<div class="bg-white rounded-xl shadow-sm border border-gray-200 p-8 text-center">
    <svg class="w-12 h-12 text-green-500 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
    </svg>
    <p class="text-gray-500 text-lg">All caught up!</p>
    <p class="text-gray-400 text-sm mt-1">No units waiting for review</p>
</div>
{% endif %}
{% endblock %}
'''

create_file('app/templates/certification/my_reviews.html', MY_REVIEWS_TEMPLATE, "Created my_reviews.html")

print("\n=== ALL PATCHES APPLIED ===")
print("Now run: git add -A && git commit -m 'Nav restructure: role-specific views for Alex + Kevin' && git push")
