#!/usr/bin/env python3
"""v313 -- fix Completed bucket count vs render divergence in live monitor.

Defines done_statuses once at top of the unit-panel, references from both
the count formula (line ~197) and the card render filter (line ~203).
Eliminates the exclusion-vs-inclusion divergence that caused paused units
to be counted as Completed but not rendered.

Also expands the done set from 3 to 6 statuses per STATUS_FLOWS.md:
  submitted, reviewed, approved, pending_followup, certified, closed

Paused stays in the In Progress bucket (lines 98 + 104 already handle it).

Idempotent: re-running is a no-op once applied.
"""
from pathlib import Path
from jinja2 import Environment, TemplateSyntaxError

FILE = Path('app/templates/batches/live_monitor_data.html')
content = FILE.read_text()
original = content

# === OP 1: insert done_statuses set after unit-panel div opens ===
OLD_1 = '<div class="unit-panel">\n    {# === ACTIVE CARDS === #}'
NEW_1 = (
    '<div class="unit-panel">\n'
    "    {% set done_statuses = ['submitted','reviewed','approved',"
    "'pending_followup','certified','closed'] %}\n"
    '    {# === ACTIVE CARDS === #}'
)

if NEW_1 in content:
    print('OP 1: already applied (idempotent skip)')
else:
    assert OLD_1 in content, 'OP 1: anchor not found'
    assert content.count(OLD_1) == 1, (
        f'OP 1: expected 1 match, got {content.count(OLD_1)}'
    )
    content = content.replace(OLD_1, NEW_1)
    print('OP 1: inserted done_statuses set')

# === OP 2: rewrite completed_count formula (line ~197) ===
OLD_2 = (
    "{% set completed_count = units"
    "|rejectattr('insp_status', 'equalto', 'in_progress')"
    "|rejectattr('insp_status', 'equalto', 'not_started')"
    "|list|length %}"
)
NEW_2 = (
    "{% set completed_count = units"
    "|selectattr('insp_status', 'in', done_statuses)"
    "|list|length %}"
)

if NEW_2 in content:
    print('OP 2: already applied (idempotent skip)')
else:
    assert OLD_2 in content, 'OP 2: anchor not found'
    assert content.count(OLD_2) == 1, (
        f'OP 2: expected 1 match, got {content.count(OLD_2)}'
    )
    content = content.replace(OLD_2, NEW_2)
    print('OP 2: rewrote completed_count formula')

# === OP 3: rewrite card render filter (line ~203) ===
OLD_3 = "{% if u.insp_status in ['submitted','reviewed','approved'] %}"
NEW_3 = "{% if u.insp_status in done_statuses %}"

if NEW_3 in content:
    print('OP 3: already applied (idempotent skip)')
else:
    assert OLD_3 in content, 'OP 3: anchor not found'
    assert content.count(OLD_3) == 1, (
        f'OP 3: expected 1 match, got {content.count(OLD_3)}'
    )
    content = content.replace(OLD_3, NEW_3)
    print('OP 3: rewrote card render filter')

# === Jinja syntax check (parses string, no file lookups) ===
try:
    Environment().parse(content)
    print('jinja syntax: OK')
except TemplateSyntaxError as e:
    print(f'JINJA ERROR (file NOT written): {e}')
    raise SystemExit(1)

# === write file ===
if content != original:
    FILE.write_text(content)
    print(f'wrote {FILE} ({len(content)} chars)')
else:
    print('no changes (all ops were no-ops)')
