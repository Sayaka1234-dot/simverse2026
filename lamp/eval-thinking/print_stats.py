import json
from pathlib import Path

for p in Path('eval-thinking/results').rglob('model_summary.json'):
    data = json.loads(p.read_text('utf-8'))
    overall = data['overall']
    model = p.parent.name
    solved = overall['solved_tasks']
    total = overall['total_tasks']
    rate = overall['solution_rate'] * 100
    print(f"{model}: {solved}/{total} ({rate:.1f}%)")
