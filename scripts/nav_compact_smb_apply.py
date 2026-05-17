#!/usr/bin/env python3
"""
Apply the same compact top-nav Tailwind changes from base.html to
site_meeting_brief.html (which duplicates base.html's nav HTML structure).

4 sub-changes:
  1. Nav links: text-sm -> text-xs
  2. Nav-links container gap: space-x-4 -> space-x-3
  3. Logout: text-sm -> text-xs
  4. User name: text-sm -> text-xs

Data Quality templates don't need fixing — they extend base.html.

Run from repo root: python3 scripts/nav_compact_smb_apply.py
"""

from pathlib import Path

SMB = Path("app/templates/analytics/site_meeting_brief.html")


def replace_all(path, old, new, label):
    text = path.read_text()
    count = text.count(old)
    assert count > 0, f"{label}: no matches found in {path}"
    path.write_text(text.replace(old, new))
    after = path.read_text()
    assert after.count(new) >= count, f"{label}: post-write count mismatch"
    assert after.count(old) == 0, f"{label}: old still present"
    print(f"OK  {label} ({count} repl)")


def replace_once(path, old, new, label):
    text = path.read_text()
    count = text.count(old)
    assert count == 1, f"{label}: expected 1 match, found {count}"
    path.write_text(text.replace(old, new))
    after = path.read_text()
    assert after.count(new) == 1, f"{label}: post-write missing new string"
    assert after.count(old) == 0, f"{label}: old still present"
    print(f"OK  {label}")


# 1. Nav links text-sm -> text-xs
replace_all(
    SMB,
    'class="text-sm text-gray-300 hover:text-white"',
    'class="text-xs text-gray-300 hover:text-white"',
    "SMB: nav links text-sm -> text-xs",
)

# 2. Nav-links container gap
replace_once(
    SMB,
    'class="hidden md:flex items-center space-x-4"',
    'class="hidden md:flex items-center space-x-3"',
    "SMB: nav-links container gap",
)

# 3. Logout link
replace_once(
    SMB,
    'class="hidden md:inline text-sm text-gray-300 hover:text-white"',
    'class="hidden md:inline text-xs text-gray-300 hover:text-white"',
    "SMB: logout link",
)

# 4. User name span
replace_once(
    SMB,
    'class="text-sm text-gray-300 hidden sm:inline"',
    'class="text-xs text-gray-300 hidden sm:inline"',
    "SMB: user name",
)

print("\nSMB nav changes applied. Verify with grep, then commit.")
