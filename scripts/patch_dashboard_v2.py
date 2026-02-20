"""
Patch: Replace dashboard() function in analytics.py with enriched v2 version.
Run from repo root: python3 scripts/patch_dashboard_v2.py

Requires: scripts/dashboard_function_v2.py (the replacement function)
"""
import os
import sys

analytics_path = 'app/routes/analytics.py'
function_path = 'scripts/dashboard_function_v2.py'

if not os.path.exists(analytics_path):
    print(f"ERROR: {analytics_path} not found. Run from repo root.")
    sys.exit(1)
if not os.path.exists(function_path):
    print(f"ERROR: {function_path} not found.")
    sys.exit(1)

# Read both files
with open(analytics_path, 'r') as f:
    lines = f.readlines()
with open(function_path, 'r') as f:
    new_function = f.read()

# Find dashboard function: starts at @analytics_bp.route('/')
# Ends just before @analytics_bp.route('/<block_slug>/<int:floor>')
start_idx = None
end_idx = None
for i, line in enumerate(lines):
    if "@analytics_bp.route('/')" in line and 'block_slug' not in line:
        start_idx = i
    elif start_idx is not None and "@analytics_bp.route('/<block_slug>" in line:
        end_idx = i
        break

if start_idx is None or end_idx is None:
    print(f"ERROR: Could not find dashboard function boundaries")
    print(f"  start: {start_idx}, end: {end_idx}")
    sys.exit(1)

old_line_count = end_idx - start_idx
print(f"Found dashboard() at lines {start_idx+1}-{end_idx}")
print(f"Old function: {old_line_count} lines")

# Splice: keep everything before start_idx, insert new function, keep everything from end_idx
before = lines[:start_idx]
after = lines[end_idx:]

# Ensure new function ends with two newlines before next decorator
if not new_function.endswith('\n\n'):
    new_function = new_function.rstrip('\n') + '\n\n\n'

new_content = ''.join(before) + new_function + ''.join(after)

# Write back
with open(analytics_path, 'w') as f:
    f.write(new_content)

new_line_count = new_function.count('\n')
print(f"New function: {new_line_count} lines")
print(f"Replacement complete.")

# Verify
import py_compile
try:
    py_compile.compile(analytics_path, doraise=True)
    print("Syntax: OK")
except py_compile.PyCompileError as e:
    print(f"Syntax ERROR: {e}")
    sys.exit(1)

# Check key markers
with open(analytics_path, 'r') as f:
    content = f.read()

checks = [
    ('inspected_zone_map', 'Inspected per zone query'),
    ('default=0)', 'max_round default fixed'),
    ("'inspected': inspected,", 'Inspected in card dict'),
    ('median_defects', 'Median computation'),
    ("card['inspected'] > 0", 'Active blocks logic'),
    ('floor_labels=FLOOR_LABELS', 'Floor labels passed'),
]
print("\nVerification:")
all_ok = True
for marker, label in checks:
    found = marker in content
    status = 'OK' if found else 'MISSING'
    if not found:
        all_ok = False
    print(f"  {label}: {status}")

if all_ok:
    print("\nAll checks passed. Ready to commit.")
else:
    print("\nWARNING: Some checks failed!")
