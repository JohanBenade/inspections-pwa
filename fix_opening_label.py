filepath = 'app/templates/analytics/rectification.html'

with open(filepath, 'r') as f:
    content = f.read()

old = '<div class="kpi-label" style="margin-top: 0;">Opening</div>'
new = '<div class="kpi-label" style="margin-top: 0;">Open defects</div>'

assert old in content, "MATCH FAILED"
content = content.replace(old, new, 1)

with open(filepath, 'w') as f:
    f.write(content)

print("OK - Opening -> Open defects")
