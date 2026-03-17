filepath = 'app/templates/analytics/rectification.html'

with open(filepath, 'r') as f:
    content = f.read()

old = '    {% set has_data = True %}{# TEMP: force preview with fabricated data #}\n    {% if not has_data %}'

new = '''    {# TEMP: force preview with fabricated data #}
    {% set has_data = True %}
    {% set kpis = {'total_inspected': 48, 'units_reinspected': 16, 'c1_reviewed': 396, 'c1_cleared': 277, 'c1_still_open': 119, 'new_in_c2': 23, 'net_improvement': 254, 'net_pct': 64.1, 'clearance_rate': 69.9, 'avg_rect_days': 8.2, 'avg_rect_days_available': True, 'max_cycle_num': 2} %}
    {% if not has_data %}'''

assert old in content, "MATCH FAILED"
content = content.replace(old, new, 1)

with open(filepath, 'w') as f:
    f.write(content)

print("OK - fake kpis injected for preview")
