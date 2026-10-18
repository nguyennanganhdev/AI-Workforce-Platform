import { existsSync } from 'node:fs';
import { registerHooks } from 'node:module';
import { fileURLToPath } from 'node:url';

// Match Vite's @/ alias for Node's native TypeScript test runner.
registerHooks({
	resolve(specifier, context, nextResolve) {
		if (specifier.startsWith('@/')) {
			const base = new URL(`../src/${specifier.slice(2)}`, import.meta.url);
			for (const suffix of ['', '.ts', '.tsx', '/index.ts']) {
				const url = new URL(base.href + suffix);
				if (existsSync(fileURLToPath(url))) return nextResolve(url.href, context);
			}
		}
		return nextResolve(specifier, context);
	},
});
