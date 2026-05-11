"""
Step 6.7: State-aware latent indicator on my_reviews TL queue

Changes (2 files, 2 logical changes):
  1. certification.py my_reviews query: replace single latent_count subquery
     with latent_open_count + latent_rectified_count (unit-scoped).
  2. my_reviews.html template: replace single latent indicator with
     tri-state conditional (red +M latent open / green latent rectified /
     nothing).

Idempotent: detects already-migrated state and exits cleanly.
All asserts run before any file is written -- no partial-state risk.

Run from project root:
    python3 step6_7_latent_queue_indicator.py
"""
import sys

cert_path = 'app/routes/certification.py'
template_path = 'app/templates/certification/my_reviews.html'

with open(cert_path) as f:
    cert = f.read()
with open(template_path) as f:
    template = f.read()

# === IDEMPOTENCY CHECK ===
already_in_cert = 'latent_open_count' in cert
already_in_template = 'latent_open_count' in template

if already_in_cert and already_in_template:
    print('Already migrated. Both files contain Step 6.7 content. Exiting.')
    sys.exit(0)
elif already_in_cert or already_in_template:
    print('PARTIAL STATE detected -- one file migrated, the other not.')
    print('  certification.py migrated: {}'.format(already_in_cert))
    print('  my_reviews.html migrated: {}'.format(already_in_template))
    print('Manual inspection required. Exiting without changes.')
    sys.exit(1)

# === CHANGE 1: Split latent_count subquery into open + rectified counts (unit-scoped) ===
old_subquery = """               (SELECT COUNT(*) FROM latent_area_note lan
                WHERE lan.inspection_id = i.id
                AND lan.tenant_id = i.tenant_id) AS latent_count"""

new_subquery = """               (SELECT COUNT(*) FROM latent_area_note lan
                WHERE lan.unit_id = u.id
                AND lan.tenant_id = i.tenant_id
                AND lan.rectified_at_cycle_number IS NULL) AS latent_open_count,
               (SELECT COUNT(*) FROM latent_area_note lan
                WHERE lan.unit_id = u.id
                AND lan.tenant_id = i.tenant_id
                AND lan.rectified_at_cycle_number IS NOT NULL) AS latent_rectified_count"""

assert old_subquery in cert, "CHANGE 1: latent_count subquery not found in certification.py"
assert cert.count(old_subquery) == 1, \
    "CHANGE 1: expected exactly 1 occurrence, found {}".format(cert.count(old_subquery))

# === CHANGE 2: Replace template indicator with tri-state conditional ===
old_indicator = '''<span class="text-xs font-medium text-gray-700">{{ insp.defect_count }} defect{{ 's' if insp.defect_count != 1 }}{% if insp.latent_count %} &middot; +{{ insp.latent_count }} latent{% endif %}</span>'''

new_indicator = '''<span class="text-xs font-medium text-gray-700">{{ insp.defect_count }} defect{{ 's' if insp.defect_count != 1 }}{% if insp.latent_open_count %} &middot; <span class="text-red-600">+{{ insp.latent_open_count }} latent open</span>{% elif insp.latent_rectified_count %} &middot; <span class="text-green-600">latent rectified</span>{% endif %}</span>'''

assert old_indicator in template, "CHANGE 2: latent indicator span not found in template"
assert template.count(old_indicator) == 1, \
    "CHANGE 2: expected exactly 1 occurrence, found {}".format(template.count(old_indicator))

# === ALL ASSERTS PASSED -- APPLY ALL CHANGES IN MEMORY ===
cert = cert.replace(old_subquery, new_subquery)
print('CHANGE 1 applied: latent_count subquery split into open + rectified (unit-scoped)')

template = template.replace(old_indicator, new_indicator)
print('CHANGE 2 applied: queue indicator now tri-state (open red / rectified green / hidden)')

# === FINAL WRITE ===
with open(cert_path, 'w') as f:
    f.write(cert)
with open(template_path, 'w') as f:
    f.write(template)

print()
print('=== STEP 6.7 COMPLETE ===')
print('Files modified:')
print('  ', cert_path)
print('  ', template_path)
