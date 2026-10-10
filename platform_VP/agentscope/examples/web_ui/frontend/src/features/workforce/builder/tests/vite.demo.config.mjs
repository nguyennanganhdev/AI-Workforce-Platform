// Isolated demo config; no changes to the shared Vite config or application routes.
import { fileURLToPath } from 'node:url';

import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
	root: fileURLToPath(new URL('../../../../../', import.meta.url)),
	plugins: [react(), tailwindcss()],
	resolve: { alias: { '@': fileURLToPath(new URL('../../../../', import.meta.url)) } },
});
