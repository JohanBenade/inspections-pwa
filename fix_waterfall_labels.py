filepath = 'app/templates/analytics/rectification.html'

with open(filepath, 'r') as f:
    content = f.read()

old = "labels: ['Opening\nbalance', 'Rectified', 'New\ndefects', 'Closing\nbalance'],"

new = "labels: ['Opening\\nbalance', 'Rectified', 'New\\ndefects', 'Closing\\nbalance'],"

assert old in content, "MATCH FAILED"
content = content.replace(old, new, 1)

with open(filepath, 'w') as f:
    f.write(content)

print("OK - fixed newline escaping in chart labels")
