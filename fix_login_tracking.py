#!/usr/bin/env python3
"""
Add login tracking + admin login status page.
Run on MacBook: python3 fix_login_tracking.py
"""
import sys, os

if not os.path.exists('app/__init__.py'):
    print('ERROR: Run from project root')
    sys.exit(1)

errors = []

# =============================================================
# 1. Update login function to track last_login
# =============================================================
print('--- Updating app/__init__.py ---')
with open('app/__init__.py', 'r') as f:
    content = f.read()

old_login = """            if user:
                session['user_id'] = user['id']
                session['user_name'] = user['name']
                session['role'] = user['role']
                session['tenant_id'] = user['tenant_id']
                return redirect(url_for('home'))"""

new_login = """            if user:
                session['user_id'] = user['id']
                session['user_name'] = user['name']
                session['role'] = user['role']
                session['tenant_id'] = user['tenant_id']
                # Track login timestamp
                from datetime import datetime, timezone
                db.execute("UPDATE inspector SET last_login = ? WHERE id = ?",
                           [datetime.now(timezone.utc).isoformat(), user['id']])
                db.commit()
                return redirect(url_for('home'))"""

if old_login in content:
    content = content.replace(old_login, new_login, 1)
    with open('app/__init__.py', 'w') as f:
        f.write(content)
    print('  Login tracking added')
else:
    errors.append('Could not find login block in __init__.py')

# =============================================================
# 2. Add admin route for login status
# =============================================================
print('\n--- Updating app/routes/analytics.py ---')
with open('app/routes/analytics.py', 'r') as f:
    content = f.read()

# Find the end of the file to append the new route
route_code = """

@analytics_bp.route('/login-status')
@require_manager
def login_status():
    \"\"\"Admin view: inspector login status.\"\"\"
    tenant_id = session['tenant_id']
    inspectors = [dict(r) for r in query_db(\"\"\"
        SELECT id, name, email, role, last_login, active
        FROM inspector
        WHERE tenant_id = ? AND role = 'inspector' AND active = 1
        ORDER BY last_login DESC NULLS LAST, name
    \"\"\", [tenant_id])]

    floor_labels = {0: 'Ground', 1: '1st Floor', 2: '2nd Floor'}

    for insp in inspectors:
        # Get assigned units from latest batch
        units = [dict(r) for r in query_db(\"\"\"
            SELECT u.unit_number, u.block, u.floor
            FROM batch_unit bu
            JOIN unit u ON bu.unit_id = u.id
            JOIN inspection_batch ib ON bu.batch_id = ib.id
            WHERE bu.inspector_id = ? AND bu.tenant_id = ?
            AND ib.status IN ('open', 'in_progress')
            ORDER BY u.unit_number
        \"\"\", [insp['id'], tenant_id])]
        insp['units'] = ', '.join(u['unit_number'] for u in units) if units else 'None'
        insp['login_display'] = insp['last_login'][:16].replace('T', ' ') if insp['last_login'] else 'Never'
        insp['has_logged_in'] = insp['last_login'] is not None

    logged_in = sum(1 for i in inspectors if i['has_logged_in'])

    return render_template('analytics/login_status.html',
        inspectors=inspectors,
        logged_in=logged_in,
        total=len(inspectors))
"""

content += route_code
with open('app/routes/analytics.py', 'w') as f:
    f.write(content)
print('  login_status route added')

# =============================================================
# 3. Create template
# =============================================================
print('\n--- Creating login_status.html ---')

template = """{% extends "base.html" %}
{% block title %}Inspector Login Status{% endblock %}
{% block content %}
<div style="max-width: 800px; margin: 0 auto; padding: 1rem;">
    <h1 style="font-size: 1.5rem; font-weight: 700; margin-bottom: 0.25rem;">Inspector Login Status</h1>
    <p style="color: #6B7280; font-size: 0.875rem; margin-bottom: 1.5rem;">{{ logged_in }} of {{ total }} inspectors have logged in</p>

    <!-- Progress bar -->
    <div style="background: #E5E7EB; border-radius: 9999px; height: 8px; margin-bottom: 1.5rem;">
        <div style="background: #4A7C59; border-radius: 9999px; height: 8px; width: {{ (logged_in / total * 100) if total else 0 }}%;"></div>
    </div>

    <!-- Inspector table -->
    <table style="width: 100%; border-collapse: collapse;">
        <thead>
            <tr style="border-bottom: 2px solid #E5E7EB;">
                <th style="text-align: left; padding: 0.5rem; font-size: 0.75rem; text-transform: uppercase; color: #6B7280;">Inspector</th>
                <th style="text-align: left; padding: 0.5rem; font-size: 0.75rem; text-transform: uppercase; color: #6B7280;">Units</th>
                <th style="text-align: left; padding: 0.5rem; font-size: 0.75rem; text-transform: uppercase; color: #6B7280;">Last Login</th>
                <th style="text-align: center; padding: 0.5rem; font-size: 0.75rem; text-transform: uppercase; color: #6B7280;">Status</th>
            </tr>
        </thead>
        <tbody>
            {% for insp in inspectors %}
            <tr style="border-bottom: 1px solid #F3F4F6;">
                <td style="padding: 0.75rem 0.5rem;">
                    <div style="font-weight: 600; font-size: 0.9rem;">{{ insp.name }}</div>
                    <div style="font-size: 0.75rem; color: #9CA3AF;">{{ insp.email or 'No email' }}</div>
                </td>
                <td style="padding: 0.75rem 0.5rem; font-size: 0.85rem;">{{ insp.units }}</td>
                <td style="padding: 0.75rem 0.5rem; font-size: 0.85rem; color: {% if insp.has_logged_in %}#1A1A1A{% else %}#DC2626{% endif %};">
                    {{ insp.login_display }}
                </td>
                <td style="padding: 0.75rem 0.5rem; text-align: center;">
                    {% if insp.has_logged_in %}
                    <span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: #4A7C59;"></span>
                    {% else %}
                    <span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: #DC2626;"></span>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
"""

os.makedirs('app/templates/analytics', exist_ok=True)
with open('app/templates/analytics/login_status.html', 'w') as f:
    f.write(template)
print('  login_status.html created')

# =============================================================
# REPORT
# =============================================================
print('\n=== RESULT ===')
if errors:
    for e in errors: print(f'  ERROR: {e}')
    sys.exit(1)
else:
    print('All changes applied.')
    print('git add -A && git commit -m "Add login tracking + admin login status page" && git push')
    print('\nView at: /analytics/login-status')
