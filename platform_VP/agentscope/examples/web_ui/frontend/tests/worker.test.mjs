import assert from 'node:assert/strict';
import test from 'node:test';

import worker from '../public/_worker.js';

test('the Pages worker strips /api and rewrites auth cookies and redirects', async () => {
	const originalFetch = globalThis.fetch;
	let upstreamUrl;
	let upstreamHeaders;
	globalThis.fetch = async (url, init) => {
		upstreamUrl = String(url);
		upstreamHeaders = init.headers;
		return new Response(null, {
			status: 307,
			headers: {
				location: 'https://backend.example/auth/login?next=%2Fchat',
				'set-cookie': 'refresh=token; Path=/auth; HttpOnly; Secure',
			},
		});
	};
	try {
		const response = await worker.fetch(
			new Request('https://frontend.example/api/auth/login'),
			{ BACKEND_ORIGIN: 'https://backend.example', ORIGIN_VERIFY: 'origin-secret' },
		);
		assert.equal(upstreamUrl, 'https://backend.example/auth/login');
		assert.equal(upstreamHeaders.get('x-origin-verify'), 'origin-secret');
		assert.equal(
			response.headers.get('location'),
			'https://frontend.example/api/auth/login?next=%2Fchat',
		);
		assert.match(response.headers.get('set-cookie'), /Path=\/api\/auth/i);
	} finally {
		globalThis.fetch = originalFetch;
	}
});

test('the Pages worker delegates non-API routes to static assets', async () => {
	let requested;
	const response = await worker.fetch(new Request('https://frontend.example/chat'), {
		ASSETS: {
			fetch(request) {
				requested = request.url;
				return new Response('frontend');
			},
		},
	});
	assert.equal(requested, 'https://frontend.example/chat');
	assert.equal(await response.text(), 'frontend');
});
