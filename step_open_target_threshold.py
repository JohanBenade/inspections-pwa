import pathlib

path = pathlib.Path('app/templates/analytics/briefing.html')
content = path.read_text()

# Edit 1: page 1 open-target panel
old1 = '''  <div class="open-target">
    <div class="open-target-head">De-snag open item{{ 's' if c2_open_details|length > 1 else '' }}</div>
    <div class="open-target-body">
      {% for d in c2_open_details %}
      Unit <b>{{ d.unit_number }}</b> &middot; {{ d.block }} {{ d.floor_label }} &middot; {{ d.area }} &middot; {{ d.trade }} &middot; {{ d.count }} defect{{ 's' if d.count != 1 else '' }} not rectified.{% if loop.last %} Full detail page 5.{% endif %}{% if not loop.last %}<br>{% endif %}
      {% endfor %}
    </div>
  </div>'''

new1 = '''  <div class="open-target">
    <div class="open-target-head">De-snag open item{{ 's' if c2_still_open > 1 else '' }}</div>
    <div class="open-target-body">
      {% if c2_still_open <= 5 %}
      {% for d in c2_open_details %}
      Unit <b>{{ d.unit_number }}</b> &middot; {{ d.block }} {{ d.floor_label }} &middot; {{ d.area }} &middot; {{ d.trade }} &middot; {{ d.count }} defect{{ 's' if d.count != 1 else '' }} not rectified.{% if loop.last %} Full detail page 5.{% endif %}{% if not loop.last %}<br>{% endif %}
      {% endfor %}
      {% else %}
      {% for unit_num, entries in c2_open_details|groupby('unit_number') %}
      {% set first = entries|first %}
      {% set total = entries|sum(attribute='count') %}
      {% set areas = entries|map(attribute='area')|unique|list %}
      Unit <b>{{ unit_num }}</b> &middot; {{ first.block }} {{ first.floor_label }} &middot; {{ total }} item{{ 's' if total != 1 else '' }} not rectified &middot; {{ areas|join(', ') }}.{% if not loop.last %}<br>{% endif %}
      {% endfor %}
      {% endif %}
    </div>
  </div>'''

assert old1 in content, "Open-target panel not found"
content = content.replace(old1, new1)

# Edit 2: page 5 opening sect-sub
old2 = '''    {% if c2_still_open == 0 %}All defects rectified.
    {% else %}{{ c2_still_open }} defect{{ 's' if c2_still_open != 1 else '' }} not rectified{% if c2_open_details %} &mdash; {% for d in c2_open_details %}unit {{ d.unit_number }}, {{ d.area }}, {{ d.trade }}{% if not loop.last %}; {% endif %}{% endfor %}{% endif %}.'''

new2 = '''    {% if c2_still_open == 0 %}All defects rectified.
    {% elif c2_still_open <= 5 %}{{ c2_still_open }} defect{{ 's' if c2_still_open != 1 else '' }} not rectified{% if c2_open_details %} &mdash; {% for d in c2_open_details %}unit {{ d.unit_number }}, {{ d.area }}, {{ d.trade }}{% if not loop.last %}; {% endif %}{% endfor %}{% endif %}.
    {% else %}{{ c2_still_open }} defects not rectified. See page 1 for summary.'''

assert old2 in content, "Page 5 opening block not found"
content = content.replace(old2, new2)

# Edit 3: page 5 closing — drop inline list
old3 = '''    {{ c2_brought_forward }} defect{{ 's' if c2_brought_forward != 1 else '' }} reviewed across {{ c2_units|length }} de-snag unit{{ 's' if c2_units|length != 1 else '' }} &middot; {{ c2_cleared }} rectified &middot; {{ c2_still_open }} not rectified.{% if c2_open_details %} Not-rectified item{{ 's' if c2_open_details|length > 1 else '' }}: {% for d in c2_open_details %}unit {{ d.unit_number }} &middot; {{ d.area }} &middot; {{ d.trade }}{% if not loop.last %}; {% endif %}{% endfor %}.{% endif %}'''

new3 = '''    {{ c2_brought_forward }} defect{{ 's' if c2_brought_forward != 1 else '' }} reviewed across {{ c2_units|length }} de-snag unit{{ 's' if c2_units|length != 1 else '' }} &middot; {{ c2_cleared }} rectified &middot; {{ c2_still_open }} not rectified.'''

assert old3 in content, "Page 5 closing block not found"
content = content.replace(old3, new3)

path.write_text(content)
print('OK: open-target threshold logic applied; page 5 opening + closing cleaned')
