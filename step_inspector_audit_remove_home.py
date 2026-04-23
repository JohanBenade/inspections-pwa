import pathlib

path = pathlib.Path('app/templates/analytics/inspector_audit.html')
content = path.read_text()

old = '''        <a href="{{ url_for('home') }}" style="font-size: 0.82rem; color: #6B6B6B; text-decoration: none;">&larr; Home</a>
'''

assert old in content, "Home back-link not found"
content = content.replace(old, '')
path.write_text(content)
print("OK: Home back-link removed from inspector_audit")
