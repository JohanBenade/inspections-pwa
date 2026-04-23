import pathlib
path = pathlib.Path('app/templates/analytics/briefing.html')
content = path.read_text()

old = '''@media print {
  body { padding: 0; background: white; }
  .briefing-header { display: none; }
  .pagebreak { display: none; }
  .doc { max-width: 100%; }'''

new = '''@media print {
  body { padding: 0; background: white; }
  .briefing-header { display: none; }
  .pagebreak { display: none; }
  .page-meta { display: none; }
  .doc { max-width: 100%; }'''

assert old in content, "@media print block not found"
content = content.replace(old, new)
path.write_text(content)
print("OK: .page-meta hidden in print (Playwright header replaces it)")
