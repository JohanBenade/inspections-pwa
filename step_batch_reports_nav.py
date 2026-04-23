import pathlib

path = pathlib.Path('app/templates/base.html')
content = path.read_text()

# 1. Desktop: add Batch Reports next to Batches (broader gate)
old1 = '''                        {% if current_user.role in ['team_lead', 'manager', 'admin'] %}
                        <a href="{{ url_for('batches.list_batches') }}" class="text-sm text-gray-300 hover:text-white">Batches</a>
                        {% endif %}'''

new1 = '''                        {% if current_user.role in ['team_lead', 'manager', 'admin'] %}
                        <a href="{{ url_for('batches.list_batches') }}" class="text-sm text-gray-300 hover:text-white">Batches</a>
                        <a href="{{ url_for('analytics.batch_reports_picker') }}" class="text-sm text-gray-300 hover:text-white">Batch Reports</a>
                        {% endif %}'''

assert old1 in content, "Desktop Batches block not found"
content = content.replace(old1, new1)

# 2. Desktop: remove the now-duplicate admin-only Batch Reports line
old2 = '''                        <a href="{{ url_for('data_quality.descriptions') }}" class="text-sm text-gray-300 hover:text-white">Data Quality</a>
                        <a href="{{ url_for('analytics.batch_reports_picker') }}" class="text-sm text-gray-300 hover:text-white">Batch Reports</a>'''

new2 = '''                        <a href="{{ url_for('data_quality.descriptions') }}" class="text-sm text-gray-300 hover:text-white">Data Quality</a>'''

assert old2 in content, "Admin-only Batch Reports duplicate not found"
content = content.replace(old2, new2)

# 3. Mobile: add Batch Reports after Batches (same role gate)
old3 = '''            {% if current_user.role in ['team_lead', 'manager', 'admin'] %}
            <!-- Batches - team_lead and above -->
            <a href="{{ url_for('batches.list_batches') }}" 
               class="flex flex-col items-center text-gray-600 hover:text-primary tap-target">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                </svg>
                <span class="text-xs mt-1">Batches</span>
            </a>
            {% endif %}'''

new3 = '''            {% if current_user.role in ['team_lead', 'manager', 'admin'] %}
            <!-- Batches - team_lead and above -->
            <a href="{{ url_for('batches.list_batches') }}" 
               class="flex flex-col items-center text-gray-600 hover:text-primary tap-target">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                </svg>
                <span class="text-xs mt-1">Batches</span>
            </a>
            <!-- Batch Reports - team_lead and above -->
            <a href="{{ url_for('analytics.batch_reports_picker') }}" 
               class="flex flex-col items-center text-gray-600 hover:text-primary tap-target">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                </svg>
                <span class="text-xs mt-1">Reports</span>
            </a>
            {% endif %}'''

assert old3 in content, "Mobile Batches block not found"
content = content.replace(old3, new3)

path.write_text(content)
print("OK: Batch Reports nav added (desktop + mobile) for team_lead/manager/admin")
