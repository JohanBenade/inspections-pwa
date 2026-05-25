"""
v320 - Fix ITEMS_PER_UNIT constant from leaf-only (437) to all-rows (509)

Bug:
  app/routes/analytics.py line 41 declares ITEMS_PER_UNIT = 437, which
  is the count of LEAF item_template rows (templates with no children).
  But the 17 callsites that use this constant as a denominator for
  defect-rate calculations have a numerator (total defects) that includes
  126 defects raised against parent (container) templates during C1
  paper-import.

  This creates a denominator/numerator misalignment:
    - Denominator: 437 (leaves only)
    - Numerator: 14,320 defects total (14,194 on leaves + 126 on parents)
    - Result: ~0.88% relative inflation in all defect rates

  Diagnostic evidence (gathered 23 May 2026):
    - 509 total item_template rows = 437 leaves + 72 parents-with-children
    - 126 defects on parent templates, all 100% raised in cycle 1
      (paper-import era; PWA-tracked C2+ marks against leaves only)
    - Sample parent defects ("Sink pack: Missing a shelf",
      "Counter seating: Top edge is damaged") confirm legitimate findings

Fix:
  Change ITEMS_PER_UNIT = 437 to 509 (total item_template rows). Both
  numerator and denominator now include parents. Defect rates drop by
  ~14% relative across all 17 callsites (denominator grows 16.5% with
  numerator unchanged). This is the correction, not a regression -
  the rates were previously inflated due to the misalignment.

  Single-character constant change. No callsites need modification.

Note (deferred to follow-up):
  v317 archived one template, so the live active count is 508. Using
  509 here means new (post-v317) inspections are off by ~0.2% (1/508).
  This is negligible relative to the ~14% correction being made and is
  captured for a separate analytics.py Layer 2 audit alongside the
  batches.py denominator decision pattern.
"""

PATH = "app/routes/analytics.py"

with open(PATH, "r") as f:
    content = f.read()

old = "ITEMS_PER_UNIT = 437"
new = "ITEMS_PER_UNIT = 509"

assert old in content, "MATCH FAILED: ITEMS_PER_UNIT = 437 not found"
n = content.count(old)
assert n == 1, f"Expected exactly 1 match, found {n}"
content = content.replace(old, new)

with open(PATH, "w") as f:
    f.write(content)

print("OK: v320 patched - ITEMS_PER_UNIT 437 -> 509")
