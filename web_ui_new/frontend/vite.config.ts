import path from 'path';

import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import svgr from 'vite-plugin-svgr';

export default defineConfig({
	plugins: [react(), tailwindcss(), svgr()],
	server: {
		proxy: {
			'/api': 'http://localhost:3000',
		},
	},
	resolve: {
		alias: {
			'@': path.resolve(__dirname, './src'),
			'next/navigation': path.resolve(__dirname, './src/lib/next-navigation-shim.ts'),
		},
	},
	optimizeDeps: {
		include: ['mime-types'],
	},
	build: {
		rolldownOptions: {
			output: {
				// Libraries every page needs get their own long-cached chunks;
				// page-only libraries stay with the lazily loaded page.
				codeSplitting: {
					groups: [
						{
							name: 'react',
							test: /[\\/]node_modules[\\/](react|react-dom|scheduler|react-router|react-router-dom)[\\/]/,
						},
						{
							name: 'ui',
							test: /[\\/]node_modules[\\/](radix-ui|@radix-ui|@floating-ui|lucide-react|sonner)[\\/]/,
						},
						{
							name: 'data',
							test: /[\\/]node_modules[\\/](@tanstack|i18next|react-i18next|axios)[\\/]/,
						},
					],
				},
			},
		},
	},
});
