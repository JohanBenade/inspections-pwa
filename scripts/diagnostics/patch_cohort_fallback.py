import io

PATH = 'scripts/diagnostics/c2_cohort_27.py'
with io.open(PATH, 'r', encoding='utf-8') as f:
    content = f.read()

INTENDED = "69ce0e91"

# Site 1: anchor helper run_unit()
old1 = "    return project(u['id'], insp['cycle_id'], insp['exclusion_list_id'], floor, insp['cycle_number'])"
new1 = ("    excl = insp['exclusion_list_id'] or '" + INTENDED + "'  # intended-list fallback (link-copy gap)\n"
        "    return project(u['id'], insp['cycle_id'], excl, floor, insp['cycle_number'])")
assert old1 in content, "SITE 1 anchor return line not found"
assert content.count(old1) == 1, "SITE 1 not unique"
content = content.replace(old1, new1)

# Site 2: 27-unit loop
old2 = "    d, l, items = project(uid, insp['cycle_id'], insp['exclusion_list_id'], floor, insp['cycle_number'])"
new2 = ("    excl = insp['exclusion_list_id'] or '" + INTENDED + "'  # intended-list fallback (link-copy gap)\n"
        "    d, l, items = project(uid, insp['cycle_id'], excl, floor, insp['cycle_number'])")
assert old2 in content, "SITE 2 loop project line not found"
assert content.count(old2) == 1, "SITE 2 not unique"
content = content.replace(old2, new2)

# The link tag should still report the LIVE state (NULL vs LIST), not the fallback —
# leave the existing `link = 'NULL' if not insp['exclusion_list_id']...` line untouched.

with io.open(PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print("PATCHED both call sites with intended-list fallback '" + INTENDED + "'")
print("Verify with: grep -n \"intended-list fallback\" " + PATH)
