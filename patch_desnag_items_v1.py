"""
Patch _desnag_items.html L19: exclude items with open prior defects from
the Items-to-Inspect section. They're already rendered in the Defects
sub-section above with proper Cleared/Still Open buttons.

Run from repo root:
    python3 patch_desnag_items_v1.py

Then verify with:
    git diff app/templates/inspection/_desnag_items.html
"""
from pathlib import Path

path = Path('app/templates/inspection/_desnag_items.html')

if not path.exists():
    raise SystemExit(f'ERROR: {path} not found. Run from repo root.')

content = path.read_text()

old = "        {% if item.status != 'skipped' and (not item.is_carried_ok|default(false) or item.children_have_defects|default(false)) %}"
new = "        {% if item.status != 'skipped' and (not item.is_carried_ok|default(false) or item.children_have_defects|default(false)) and not item.has_open_prior|default(false) %}"

count = content.count(old)
assert count == 1, f'ERROR: expected exactly 1 match for old string, found {count}'
assert new not in content, 'ERROR: new string already present (already patched?)'

patched = content.replace(old, new)
path.write_text(patched)

# Verify
after = path.read_text()
assert new in after, 'ERROR: post-write verification failed'
assert old not in after, 'ERROR: old string still present after write'

print(f'OK: patched {path}')
print(f'    +1 condition: "and not item.has_open_prior|default(false)"')
