import pathlib

# 1. Remove Analytics from top nav
p1 = pathlib.Path('app/templates/base.html')
c1 = p1.read_text()

old1 = '''                        <a href="{{ url_for('analytics.login_status') }}" class="text-sm text-gray-300 hover:text-white">Login Status</a>
                        <a href="{{ url_for('analytics.dashboard') }}" class="text-sm text-gray-300 hover:text-white">Analytics</a>
                        {% if current_user.role == 'admin' %}'''

new1 = '''                        <a href="{{ url_for('analytics.login_status') }}" class="text-sm text-gray-300 hover:text-white">Login Status</a>
                        {% if current_user.role == 'admin' %}'''

assert old1 in c1, "Analytics nav link block not found"
c1 = c1.replace(old1, new1)
p1.write_text(c1)
print("OK: Analytics removed from top nav")

# 2. Remove the "← Analytics" back-link from Pipeline Dashboard
p2 = pathlib.Path('app/templates/analytics/pipeline_dashboard.html')
c2 = p2.read_text()

old2 = '''    <!-- Header -->
    <div style="margin-bottom: 1.5rem;">
        <a href="{{ url_for('analytics.dashboard') }}" style="font-size: 0.8rem; color: #9A9A9A; text-decoration: none;">&larr; Analytics</a>
        <h1 style="font-family: 'DM Sans', sans-serif; font-weight: 700; font-size: 2.25rem; letter-spacing: -0.01em; color: #1A1A1A; margin: 0.25rem 0 0 0;">'''

new2 = '''    <!-- Header -->
    <div style="margin-bottom: 1.5rem;">
        <h1 style="font-family: 'DM Sans', sans-serif; font-weight: 700; font-size: 2.25rem; letter-spacing: -0.01em; color: #1A1A1A; margin: 0.25rem 0 0 0;">'''

assert old2 in c2, "Pipeline Dashboard back-link not found"
c2 = c2.replace(old2, new2)
p2.write_text(c2)
print("OK: Analytics back-link removed from Pipeline Dashboard")
