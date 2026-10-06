"""Run Operations UI regressions in isolated Bun processes; save UTF-8 evidence."""
import json
import os
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
output = root / '.codex-artifacts/operations-ui-2026-10-06'
output.mkdir(parents=True, exist_ok=True)
bun = str(Path(os.environ['APPDATA']) / 'npm/bun.cmd') if os.name == 'nt' else 'bun'
files = [
    'operations-admin.test.tsx', 'operations-agent-trial.test.tsx',
    'operations-connections.test.tsx', 'operations-coordination.test.tsx',
    'operations-room-files.test.tsx', 'operations-private-ask.test.tsx',
    'operations-session-sources.test.tsx', 'connected-accounts-list.test.tsx',
    'connected-operations-ui.test.tsx', 'operations-schedules.test.tsx',
    'operations-field.test.tsx', 'operations-field-work.test.tsx',
    'operations-auth.test.ts', 'operations-work-items.test.ts',
    'operations-workspace.test.ts', 'vinhomes-operations.test.ts',
    'vinhomes-live-tickets.test.tsx',
]
results = []
for file in files:
    result = subprocess.run([bun, 'test', 'tests/' + file], cwd=root / 'app',
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            encoding='utf-8', errors='replace', timeout=60)
    (output / (file + '.final.log')).write_text(result.stdout, encoding='utf-8')
    results.append({'file': file, 'exit_code': result.returncode})
    print(json.dumps(results[-1]), flush=True)
(output / 'ui-test-results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
raise SystemExit(int(any(row['exit_code'] for row in results)))
