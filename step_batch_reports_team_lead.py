import pathlib

path = pathlib.Path('app/routes/analytics.py')
content = path.read_text()

# 1. Picker: admin -> team_lead
old1 = '''@analytics_bp.route('/batch-reports')
@require_admin
def batch_reports_picker():
    """Admin-only picker page listing all batches with links to their reports."""'''

new1 = '''@analytics_bp.route('/batch-reports')
@require_team_lead
def batch_reports_picker():
    """Picker page listing all batches with links to their reports."""'''

assert old1 in content, "batch_reports_picker decorator block not found"
content = content.replace(old1, new1)

# 2. Briefing HTML view: manager -> team_lead
old2 = '''@analytics_bp.route('/report/briefing/<batch_id>')
@require_manager
def batch_briefing_view(batch_id):'''

new2 = '''@analytics_bp.route('/report/briefing/<batch_id>')
@require_team_lead
def batch_briefing_view(batch_id):'''

assert old2 in content, "batch_briefing_view decorator block not found"
content = content.replace(old2, new2)

# 3. Briefing PDF: manager -> team_lead
old3 = '''@analytics_bp.route('/report/briefing/<batch_id>/pdf')
@require_manager
def batch_briefing_pdf(batch_id):'''

new3 = '''@analytics_bp.route('/report/briefing/<batch_id>/pdf')
@require_team_lead
def batch_briefing_pdf(batch_id):'''

assert old3 in content, "batch_briefing_pdf decorator block not found"
content = content.replace(old3, new3)

path.write_text(content)
print("OK: batch reports picker + briefing view + briefing PDF now allow team_lead")
