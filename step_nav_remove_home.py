import pathlib

path = pathlib.Path('app/templates/base.html')
content = path.read_text()

# 1. Desktop nav: gate Home to inspector/office_admin only
old1 = '''                    {% if current_user %}
                    <!-- Desktop nav links -->
                    <div class="hidden md:flex items-center space-x-4">
                        <a href="{{ url_for('home') }}" class="text-sm text-gray-300 hover:text-white">Home</a>'''

new1 = '''                    {% if current_user %}
                    <!-- Desktop nav links -->
                    <div class="hidden md:flex items-center space-x-4">
                        {% if current_user.role in ['inspector', 'office_admin'] %}
                        <a href="{{ url_for('home') }}" class="text-sm text-gray-300 hover:text-white">Home</a>
                        {% endif %}'''

assert old1 in content, "Desktop Home link block not found"
content = content.replace(old1, new1)

# 2. Mobile bottom nav: gate the Home tab to inspector/office_admin only
# Find the block starting at line ~144
old2 = '''            <a href="{{ url_for('home') }}" 
               class="flex flex-col items-center text-gray-600 hover:text-primary tap-target">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/>
                </svg>
                <span class="text-xs mt-1">Home</span>
            </a>'''

new2 = '''{% if current_user.role in ['inspector', 'office_admin'] %}
            <a href="{{ url_for('home') }}" 
               class="flex flex-col items-center text-gray-600 hover:text-primary tap-target">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/>
                </svg>
                <span class="text-xs mt-1">Home</span>
            </a>
            {% endif %}'''

assert old2 in content, "Mobile Home tab block not found"
content = content.replace(old2, new2)

path.write_text(content)
print("OK: Home nav link hidden for all roles except inspector/office_admin (desktop + mobile)")
