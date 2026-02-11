import os

HTML = os.path.expanduser('~/Documents/GitHub/inspections-pwa/app/templates/analytics/report.html')
with open(HTML, 'r') as f:
    lines = f.readlines()

# Find the pipeline section by line content
start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if '<!-- Connector line row -->' in line:
        start_idx = i
    if start_idx and i > start_idx and '</table>' in line:
        # Count table closes - we need the SECOND one (dots table)
        if end_idx is None:
            end_idx = i  # first </table> = connector table
        else:
            end_idx = i  # second </table> = dots table
            break

if start_idx is None or end_idx is None:
    print(f"FAIL: start={start_idx} end={end_idx}")
    exit(1)

print(f"Found pipeline block: lines {start_idx+1} to {end_idx+1}")
print(f"Replacing {end_idx - start_idx + 1} lines")

# Build replacement
replacement = """        <!-- Pipeline: table with dot cells and connector cells -->
        <table style="width: 80%; margin: 0 auto; border-collapse: collapse;">
        <tr>
            {% for label, date, done in stages %}
            <td style="text-align: center; vertical-align: top; width: 80px; padding: 0;">
                {% if done %}
                <div class="pipeline-dot-done">&#10003;</div>
                {% else %}
                <div class="pipeline-dot-empty">-</div>
                {% endif %}
                <div class="{% if done %}pipeline-label{% else %}pipeline-label-muted{% endif %}">{{ label }}</div>
                {% if date %}
                <div class="pipeline-date">{{ date }}</div>
                {% endif %}
            </td>
            {% if not loop.last %}
            {% set next_done = stages[loop.index0 + 1][2] %}
            <td style="vertical-align: top; padding: 0;">
                <div style="height: 2px; margin-top: 14px; background: {% if done and next_done %}#C8963E{% elif done %}#C8963E{% else %}#E8E6E1{% endif %};"></div>
            </td>
            {% endif %}
            {% endfor %}
        </tr>
        </table>
"""

new_lines = lines[:start_idx] + [replacement] + lines[end_idx+1:]

with open(HTML, 'w') as f:
    f.writelines(new_lines)

total = len(new_lines)
print(f"Written: {total} lines")
print("OK")
