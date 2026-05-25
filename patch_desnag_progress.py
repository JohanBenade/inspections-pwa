#!/usr/bin/env python3
"""
Patch app/templates/inspection/_desnag_progress.html for Step 3.

Changes:
1. Fallback variable: total_bfwd -> total_items.
2. Label: "defects addressed" -> "items addressed".
"""

PATH = 'app/templates/inspection/_desnag_progress.html'

with open(PATH, 'r') as f:
    content = f.read()

old_1 = "{% set p_total = progress.total if progress is defined else total_bfwd %}"
new_1 = "{% set p_total = progress.total if progress is defined else total_items %}"

assert old_1 in content, "Change 1 anchor not found"
assert content.count(old_1) == 1, f"Change 1 anchor not unique: {content.count(old_1)}"
content = content.replace(old_1, new_1)
print("OK change 1: fallback variable renamed total_bfwd -> total_items")

old_2 = "{{ p_addressed }} of {{ p_total }} defects addressed"
new_2 = "{{ p_addressed }} of {{ p_total }} items addressed"

assert old_2 in content, "Change 2 anchor not found"
assert content.count(old_2) == 1, f"Change 2 anchor not unique: {content.count(old_2)}"
content = content.replace(old_2, new_2)
print("OK change 2: label updated 'defects' -> 'items'")

remaining = content.count('total_bfwd')
assert remaining == 0, f"total_bfwd still present: {remaining} occurrence(s)"
print("OK sanity: no total_bfwd references remain in _desnag_progress.html")

with open(PATH, 'w') as f:
    f.write(content)

print()
print("All 2 changes applied to", PATH)
