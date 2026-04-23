import pathlib

path = pathlib.Path('app/templates/analytics/briefing.html')
content = path.read_text()

# 1. Merge old pages 3+4 into single merged page 3
old = '''<section class="page">
  <div class="page-meta"><span class="batch-id">{{ batch.name }}</span><span>Page 3 &mdash; Defects by area</span></div>

  {% if area_data %}
  <div class="sect-title">{{ "{:,}".format(c1_total_defects) }} snag defects across {{ area_data|length }} area{{ 's' if area_data|length != 1 else '' }}</div>
  <div class="sect-sub">Total across {{ c1_unit_count }} C1 unit{{ 's' if c1_unit_count != 1 else '' }}.</div>

  {% for a in area_data %}
  <div class="bar-row heavy">
    <div class="bar-name"><b>{{ a.area }}</b></div>
    <div class="bar-track"><div class="bar-fill{% if loop.index > 2 %} light{% endif %}" style="width: {{ a.bar_pct }}%;"></div></div>
    <div class="bar-val"><span class="pct">{{ a.pct }}%</span><b>{{ a.count }}</b></div>
  </div>
  {% endfor %}
  {% else %}
  <div class="sect-title">Defects by area</div>
  <div class="sect-sub">No snag inspections yet in this batch.</div>
  {% endif %}
</section>

<div class="pagebreak">&mdash; &mdash; &mdash;</div>

{# ============ PAGE 4 \u2014 BY TRADE ============ #}
<section class="page">
  <div class="page-meta"><span class="batch-id">{{ batch.name }}</span><span>Page 4 &mdash; Defects by trade</span></div>

  {% if trade_data %}
  <div class="sect-title">{{ "{:,}".format(c1_total_defects) }} snag defects across {{ trade_data|length }} trade{{ 's' if trade_data|length != 1 else '' }}</div>
  <div class="sect-sub">Total across {{ c1_unit_count }} C1 unit{{ 's' if c1_unit_count != 1 else '' }}.</div>

  {% for t in trade_data %}
  <div class="bar-row heavy">
    <div class="bar-name"><b>{{ t.trade }}</b></div>
    <div class="bar-track"><div class="bar-fill{% if loop.index > 2 %} light{% endif %}" style="width: {{ t.bar_pct }}%;"></div></div>
    <div class="bar-val"><span class="pct">{{ t.pct }}%</span><b>{{ t.count }}</b></div>
  </div>
  {% endfor %}
  {% else %}
  <div class="sect-title">Defects by trade</div>
  <div class="sect-sub">No snag inspections yet in this batch.</div>
  {% endif %}
</section>'''

new = '''<section class="page">
  <div class="page-meta"><span class="batch-id">{{ batch.name }}</span><span>Page 3 &mdash; Defects by area and trade</span></div>

  {% if area_data or trade_data %}
  <div class="sect-title">{{ "{:,}".format(c1_total_defects) }} snag defects across {{ area_data|length }} area{{ 's' if area_data|length != 1 else '' }} and {{ trade_data|length }} trade{{ 's' if trade_data|length != 1 else '' }}</div>
  <div class="sect-sub">Total across {{ c1_unit_count }} C1 unit{{ 's' if c1_unit_count != 1 else '' }}.</div>

  {% if area_data %}
  <div class="section-label">By area</div>
  {% for a in area_data %}
  <div class="bar-row heavy">
    <div class="bar-name"><b>{{ a.area }}</b></div>
    <div class="bar-track"><div class="bar-fill{% if loop.index > 2 %} light{% endif %}" style="width: {{ a.bar_pct }}%;"></div></div>
    <div class="bar-val"><span class="pct">{{ a.pct }}%</span><b>{{ a.count }}</b></div>
  </div>
  {% endfor %}
  {% endif %}

  {% if trade_data %}
  <div class="section-label">By trade</div>
  {% for t in trade_data %}
  <div class="bar-row heavy">
    <div class="bar-name"><b>{{ t.trade }}</b></div>
    <div class="bar-track"><div class="bar-fill{% if loop.index > 2 %} light{% endif %}" style="width: {{ t.bar_pct }}%;"></div></div>
    <div class="bar-val"><span class="pct">{{ t.pct }}%</span><b>{{ t.count }}</b></div>
  </div>
  {% endfor %}
  {% endif %}
  {% else %}
  <div class="sect-title">Defects by area and trade</div>
  <div class="sect-sub">No snag inspections yet in this batch.</div>
  {% endif %}
</section>'''

assert old in content, "Page 3+4 block not found"
content = content.replace(old, new)

assert 'Page 5 &mdash; Snag units' in content, "Page 5 label not found"
content = content.replace('Page 5 &mdash; Snag units', 'Page 4 &mdash; Snag units')

assert 'Page 6 &mdash; De-snag results' in content, "Page 6 label not found"
content = content.replace('Page 6 &mdash; De-snag results', 'Page 5 &mdash; De-snag results')

assert 'Page 7 &mdash; Exclusions' in content, "Page 7 label not found"
content = content.replace('Page 7 &mdash; Exclusions', 'Page 6 &mdash; Exclusions')

assert '{# ============ PAGE 5 \u2014 SNAG UNITS ============ #}' in content, "PAGE 5 comment not found"
content = content.replace(
    '{# ============ PAGE 5 \u2014 SNAG UNITS ============ #}',
    '{# ============ PAGE 4 \u2014 SNAG UNITS ============ #}'
)

assert '{# ============ PAGE 6 \u2014 DE-SNAG RESULTS ============ #}' in content, "PAGE 6 comment not found"
content = content.replace(
    '{# ============ PAGE 6 \u2014 DE-SNAG RESULTS ============ #}',
    '{# ============ PAGE 5 \u2014 DE-SNAG RESULTS ============ #}'
)

assert '{# ============ PAGE 7 \u2014 EXCLUSIONS ============ #}' in content, "PAGE 7 comment not found"
content = content.replace(
    '{# ============ PAGE 7 \u2014 EXCLUSIONS ============ #}',
    '{# ============ PAGE 6 \u2014 EXCLUSIONS ============ #}'
)

assert 'Full detail page 6.' in content, "Cross-reference not found"
content = content.replace('Full detail page 6.', 'Full detail page 5.')

path.write_text(content)
print('OK: merged pages 3+4, renumbered downstream pages, updated cross-reference')
