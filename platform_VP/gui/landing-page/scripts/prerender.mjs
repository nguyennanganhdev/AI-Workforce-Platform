import { readFile, writeFile, readdir } from 'node:fs/promises';
import { render } from '../.artifacts/prerender/prerender.js';

const file = new URL('../dist/index.html', import.meta.url);
const html = await readFile(file, 'utf8');
// The HTML template already supplies the responsive hero preload.
const markup = render().replace(/<link\b[^>]*rel="preload"[^>]*>/g, '');
if (!html.includes('<div id="root"></div>')) throw new Error('Prerender mount was not found');
const files = await readdir(new URL('../dist/build/', import.meta.url));
const criticalFonts = files.filter(name => /^be-vietnam-pro-(?:latin|vietnamese)-(?:400|900)-normal-.*\.woff2$/.test(name));
const preload = criticalFonts.map(name => `<link rel="preload" as="font" type="font/woff2" crossorigin href="/landing-assets/build/${name}">`).join('');
await writeFile(file, html.replace('</head>', `${preload}</head>`).replace('<div id="root"></div>', `<div id="root">${markup}</div>`));
console.log('React prerender: complete HTML with client hydration.');
