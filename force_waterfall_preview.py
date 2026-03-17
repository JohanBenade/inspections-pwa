filepath = 'app/templates/analytics/rectification.html'

with open(filepath, 'r') as f:
    content = f.read()

old = '    {% if not has_data %}'
new = '    {% set has_data = True %}{# TEMP: force preview with fabricated data #}\n    {% if not has_data %}'

assert old in content, "MATCH FAILED"
content = content.replace(old, new, 1)

with open(filepath, 'w') as f:
    f.write(content)

print("OK - has_data forced True for preview")
