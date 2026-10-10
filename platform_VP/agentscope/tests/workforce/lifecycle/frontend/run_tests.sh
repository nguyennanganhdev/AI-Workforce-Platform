#!/usr/bin/env bash
# Validate in a temporary checkout without changing shared dependencies/locks.
set -euo pipefail
task_source_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)
task_frontend_dir=$(mktemp -d /tmp/wf-lifecycle-frontend.XXXXXX)
trap 'rm -rf "$task_frontend_dir"' EXIT
cp -r "$task_source_root/examples/web_ui/frontend/src" "$task_frontend_dir/src"
cp "$task_source_root/examples/web_ui/frontend/package.json" "$task_frontend_dir/"
cp "$task_source_root"/examples/web_ui/frontend/tsconfig*.json "$task_frontend_dir/"
cp "$task_source_root/examples/web_ui/frontend/eslint.config.js" "$task_frontend_dir/"
mkdir -p "$task_frontend_dir/tests"
cp "$task_source_root"/tests/workforce/lifecycle/frontend/*.ts* "$task_frontend_dir/tests/"
sed -i 's@../../../../examples/web_ui/frontend/src/features/workforce/agents@../src/features/workforce/agents@g' "$task_frontend_dir/tests/agents.test.tsx"
npm install --prefix "$task_frontend_dir" --ignore-scripts --package-lock=false \
    --no-audit --no-fund --no-save @testing-library/react jsdom tsx
cd "$task_frontend_dir"
./node_modules/.bin/tsx --tsconfig tsconfig.app.json --test tests/agents.test.tsx
./node_modules/.bin/eslint src/features/workforce/agents
./node_modules/.bin/tsc --project tsconfig.app.json --noEmit
