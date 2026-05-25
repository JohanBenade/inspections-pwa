"""
v322 Patch A — app/routes/analytics.py
Add handover_ready_count to data layer.

Two changes inside _build_pipeline_report_data:
  1. Compute handover_ready_count after certified_count (Python-only, uses existing dicts)
  2. Add 'handover_ready' to metrics dict
  3. Surface 'handover_ready' in kpi dict

Operational definition: inspected units with zero open defects (snapshot-gated).
Parallel field to existing strict 'certified' — does not touch existing tracks.
"""
import io

path = 'app/routes/analytics.py'
with io.open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# --- Change 1: compute handover_ready_count + add to metrics dict ---
old1 = '''    # Headline metrics
    units_inspected = len(unit_max_completed)
    certified_count = sum(1 for u in all_units if u['certified_at'])

    # Cycle efficiency metrics (all None until C2+ data exists)
    metrics = {
        'certified': certified_count,'''

new1 = '''    # Headline metrics
    units_inspected = len(unit_max_completed)
    certified_count = sum(1 for u in all_units if u['certified_at'])
    # v322: HANDOVER-READY = inspected units with zero open defects (loose certification)
    handover_ready_count = sum(
        1 for uid in unit_max_completed.keys()
        if unit_open.get(uid, 0) == 0
    )

    # Cycle efficiency metrics (all None until C2+ data exists)
    metrics = {
        'certified': certified_count,
        'handover_ready': handover_ready_count,'''

assert old1 in content, "PATCH A.1 MATCH FAILED: certified_count + metrics block"
assert content.count(old1) == 1, "PATCH A.1 NOT UNIQUE"
content = content.replace(old1, new1)

# --- Change 2: surface handover_ready in kpi dict ---
old2 = """    kpi = {
        'units_inspected': units_inspected,
        'total_units': total_units,
        'pct_complete': round(units_inspected / total_units * 100) if total_units else 0,
        'open_defects': total_open_defects,
        'certified': metrics['certified'],"""

new2 = """    kpi = {
        'units_inspected': units_inspected,
        'total_units': total_units,
        'pct_complete': round(units_inspected / total_units * 100) if total_units else 0,
        'open_defects': total_open_defects,
        'certified': metrics['certified'],
        'handover_ready': metrics['handover_ready'],"""

assert old2 in content, "PATCH A.2 MATCH FAILED: kpi dict block"
assert content.count(old2) == 1, "PATCH A.2 NOT UNIQUE"
content = content.replace(old2, new2)

with io.open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print('PATCH v322a APPLIED: analytics.py - handover_ready data layer')
