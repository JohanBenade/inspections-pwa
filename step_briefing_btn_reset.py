import pathlib

path = pathlib.Path('app/templates/analytics/briefing.html')
content = path.read_text()

old = '''<a href="{{ url_for('analytics.batch_briefing_pdf', batch_id=batch.id) }}" class="btn btn-pdf" onclick="this.textContent='Preparing...'; this.style.opacity='0.7'; this.style.pointerEvents='none';">Download PDF</a>'''

new = '''<a href="{{ url_for('analytics.batch_briefing_pdf', batch_id=batch.id) }}" class="btn btn-pdf" onclick="var b=this; b.textContent='Preparing...'; b.style.opacity='0.7'; b.style.pointerEvents='none'; setTimeout(function(){ b.textContent='Download PDF'; b.style.opacity='1'; b.style.pointerEvents='auto'; }, 5000);">Download PDF</a>'''

assert old in content, "Briefing download button not found"
content = content.replace(old, new)

path.write_text(content)
print('OK: briefing download button now resets after 5s')
