#!/usr/bin/env python3
"""
Follow-up extraction: SMB route handlers, data builder, fortnight cadence helpers.
Writes /tmp/smb_dump2.txt.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent
path = REPO / "app/routes/analytics.py"
text = path.read_text(encoding="utf-8")
lines = text.split("\n")

def_pat = re.compile(r"^def (\w+)\(")
def_lines = []
for i, line in enumerate(lines):
    m = def_pat.search(line)
    if m:
        def_lines.append((i, m.group(1)))


def extract_block(def_line_idx):
    start = def_line_idx
    while start > 0 and lines[start - 1].startswith("@"):
        start -= 1
    j = def_line_idx + 1
    while j < len(lines):
        ln = lines[j]
        if ln == "" or ln.startswith((" ", "\t")):
            j += 1
            continue
        break
    return "\n".join(lines[start:j])


NAME_PATTERNS = [
    re.compile(r"^site_meeting_brief"),
    re.compile(r"^_build_brief"),
]
BODY_PATTERNS = ["site_meeting_brief.html", "site-meeting-brief"]
CADENCE_KEYWORDS = ["snap", "cutoff", "monday", "fortnight"]

out = []
seen = set()

# First pass: name or body match
for line_idx, name in def_lines:
    if name in seen:
        continue
    block = extract_block(line_idx)
    reason = None
    for p in NAME_PATTERNS:
        if p.search(name):
            reason = f"name: {p.pattern}"
            break
    if not reason:
        for s in BODY_PATTERNS:
            if s in block:
                reason = f"body: contains '{s}'"
                break
    if reason:
        out.append(f"\n{'='*78}\nFUNCTION: {name} (line {line_idx + 1})\nREASON: {reason}\n{'='*78}\n{block}\n")
        seen.add(name)

# Second pass: cadence-related helpers (catch _last_monday, _fortnight_cutoff, etc.)
for line_idx, name in def_lines:
    if name in seen:
        continue
    if any(kw in name.lower() for kw in CADENCE_KEYWORDS):
        block = extract_block(line_idx)
        out.append(f"\n{'='*78}\nFUNCTION: {name} (line {line_idx + 1})\nREASON: cadence-keyword in name\n{'='*78}\n{block}\n")
        seen.add(name)

# Module-level imports for context (first 50 lines)
out.insert(0, f"\n{'='*78}\nFILE HEAD (imports + module-level)\n{'='*78}\n"
              + "\n".join(lines[:50]) + "\n")

output = "".join(out)
out_path = Path("/tmp/smb_dump2.txt")
out_path.write_text(output, encoding="utf-8")
print(f"Wrote {out_path}")
print(f"Size: {len(output)} chars")
print(f"Functions extracted: {len(seen)}")
for n in sorted(seen):
    print(f"  - {n}")
