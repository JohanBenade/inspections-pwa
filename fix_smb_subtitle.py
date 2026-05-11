#!/usr/bin/env python3
"""
fix_smb_subtitle.py
Add 'four-bed' qualifier to the Site Meeting Brief subtitle to clarify
that analytics cover four-bed units only.

Single-line text change in app/templates/analytics/site_meeting_brief.html
(currently line 334):

  before: Power Park Student Housing &mdash; Phase 3 &mdash; 191 Units
  after:  Power Park Student Housing &mdash; Phase 3 &mdash; 191 four-bed Units
"""
from pathlib import Path

TARGET = Path("app/templates/analytics/site_meeting_brief.html")

OLD = 'Power Park Student Housing &mdash; Phase 3 &mdash; 191 Units'
NEW = 'Power Park Student Housing &mdash; Phase 3 &mdash; 191 four-bed Units'

content = TARGET.read_text()

# Pre-flight assertions
assert OLD in content, f"Anchor not found in {TARGET}: {OLD!r}"
count_before = content.count(OLD)
assert count_before == 1, (
    f"Anchor not unique in {TARGET} (count={count_before}); "
    f"refusing to write."
)

# Apply
content_new = content.replace(OLD, NEW)
TARGET.write_text(content_new)

# Post-flight assertions
after = TARGET.read_text()
assert NEW in after, "Replacement string not present after write."
assert OLD not in after, "Old string still present after write."

print("OK: SMB subtitle updated.")
print(f"  {NEW}")
