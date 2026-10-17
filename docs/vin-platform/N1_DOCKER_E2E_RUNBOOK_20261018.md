# N1/N2 Docker local — linked customer, staff and confirmation

This is a repeatable local acceptance harness, not a production deployment. Domain/IdP/data/runner files belong to N1 under `vinhome_Recident/services/vinhomes-api/tests`. Real Platform factory, N2 Leader/CustomerService/card consumer, real Domain password/consent and staff app are exercised. No HTTP business response is mocked. The sole model is a bounded local scripted Chat Completions server; all fixture server connections are restricted to loopback. The dedicated Docker bridge publishes loopback ports (an internal Docker network cannot publish them on this Windows Desktop installation).

Prepare a clean integration checkout with N1 + N2 code. Never reset either person's worktree. Pass an existing **Vin-enabled** Platform frontend build from N2 and the current unchanged staff frontend build. The harness does not edit Platform compose/Dockerfile or UI. Required preinstalled images: agentscope-op2-offline-qa:20261017 (Python 3.11), vinhomes-op2-offline-qa:20261017, pgvector/pgvector:pg17, redis:7-alpine, nginx:1.27-alpine. Host driver needs httpx + Playwright with Chromium. No deployment .env is read or mounted; all credentials are fixed disposable fixture strings in the helper. These images/builds are local QA artifacts, not an RC release.

Run from the repository root with a fresh ignored output directory each time. PowerShell example (adapt Python/build paths to the host):

```powershell
$taskPython = 'E:/AI-Workforce-Platform-user2/platform_VP/agentscope/.venv/Scripts/python.exe'
$taskTests = 'vinhome_Recident/services/vinhomes-api/tests'
$taskOutput = 'E:/AI-Workforce-Platform-user1/platform_VP/agentscope/.artifacts/n1-r04-final'
$env:PYTHONIOENCODING = 'utf-8'
& $taskPython "$taskTests/run_vin_platform_docker_e2e.py" up --source E:/AI-Workforce-Platform-n1-r04-e2e --output $taskOutput
& $taskPython "$taskTests/run_vin_platform_docker_e2e.py" web --output $taskOutput --platform-dist E:/AI-Workforce-Platform-user2/platform_VP/agentscope/examples/web_ui/frontend/dist --staff-dist E:/AI-Workforce-Platform/vinhome_Recident/apps/staff-web/dist
& $taskPython "$taskTests/vin_platform_browser_roundtrip.py" --output $taskOutput
& $taskPython "$taskTests/run_vin_platform_docker_e2e.py" down --output $taskOutput
```

Reserve ports 18101–18106 and 15459 first. `up` creates only named `vin-n1-r04-e2e-<random>` containers/network, fresh PostgreSQL databases, restricted Domain runtime role, Redis, Domain, Platform and scripted model. It migrates Platform to head and Domain using real migration/seed tools. `web` serves existing builds via fixture-only reverse proxies, including refresh-cookie path rewriting. `down` verifies ownership labels, preserves logs, and removes only those containers, their anonymous volumes and the labelled network. After a failed run, inspect evidence and use `down` before another fresh run. Do not rerun browser registration against a used Domain subject: one verified subject may belong to only one Platform account.

The browser scenario registers a VIN_USER through the real form, provisions admin policy/eligibility/provider using real admin APIs, navigates to Domain's login page and submits the real consent form, returns through N2's callback, and sends chat to the private Leader. Scripted model calls CustomerService context/create using IDs returned by the Domain. No resident or owner ID is fabricated by a prompt.

Domain administrator/dispatcher then creates and assigns work through existing Domain HTTP APIs. This is a fixture dispatcher, **not proof of autonomous agent dispatch**. Technical staff signs in with a real password session and clicks Nhận việc on the actual staff app. Subsequent en-route/arrived, quote, photo evidence, completion and QC use real Domain APIs. The resident reviews and clicks both the repair approval and final completion in the existing Platform card. Each decision is replayed with the same idempotency key and must return the same receipt. Assertions require ticket closed, **canonical Domain case completed**, final resolution photos, applied progress, billed user quota and zero BQL start commands.

Outputs: `roundtrip.json`, screenshots of Domain consent/staff acceptance/Platform closure, state/provenance (source SHA + dirty paths, fixture SHA, image IDs and build-tree hashes), and service logs on cleanup. Keep raw fixture artifacts ignored. Commit only sanitized evidence. A fresh completed run is one scenario PASS, not a test count assembled from individual steps. Unit/contract/browser-fixture suites remain separate evidence.

M2 stays disabled throughout. Business UAT, real IdP/resident data, real model quality, pilot load, off-host recovery and production cutover remain separate gates. There is no Platform BQL route, dashboard, approval bridge, common Discord bot or staff workflow rewrite in this harness.
