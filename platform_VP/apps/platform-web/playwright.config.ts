import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests',
  workers: 1,
  timeout: 60000,
  use: { baseURL: 'http://127.0.0.1:3081', headless: true, trace: 'retain-on-failure' },
  webServer: [
    {
      command: 'uv run python tests/browser_server.py',
      cwd: '../../services/platform-api',
      url: 'http://127.0.0.1:8099/api/health',
      reuseExistingServer: false,
      timeout: 60000,
    },
    {
      command: 'pnpm exec vite --host 127.0.0.1 --port 3081 --config vite.acceptance.config.ts',
      url: 'http://127.0.0.1:3081',
      reuseExistingServer: false,
    },
  ],
});
