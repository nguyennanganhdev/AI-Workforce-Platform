const API_PREFIX = '/api';

function rewriteCookiePath(cookie) {
	return cookie.replace(/Path=\/auth(?=;|$)/i, 'Path=/api/auth');
}

function copyResponseHeaders(source) {
	const headers = new Headers(source);
	const getSetCookie = source.getSetCookie?.bind(source);
	const cookies = getSetCookie ? getSetCookie() : [];
	if (cookies.length) {
		headers.delete('set-cookie');
		for (const cookie of cookies) headers.append('set-cookie', rewriteCookiePath(cookie));
	} else {
		const cookie = source.get('set-cookie');
		if (cookie) headers.set('set-cookie', rewriteCookiePath(cookie));
	}
	return headers;
}

async function proxyApi(request, env) {
	if (!env.BACKEND_ORIGIN) {
		return new Response('BACKEND_ORIGIN is not configured', { status: 503 });
	}
	const incoming = new URL(request.url);
	const backend = new URL(env.BACKEND_ORIGIN);
	backend.pathname = incoming.pathname.slice(API_PREFIX.length) || '/';
	backend.search = incoming.search;

	const headers = new Headers(request.headers);
	headers.delete('host');
	if (env.ORIGIN_VERIFY) headers.set('x-origin-verify', env.ORIGIN_VERIFY);
	const upstream = await fetch(backend, {
		method: request.method,
		headers,
		body: request.method === 'GET' || request.method === 'HEAD' ? undefined : request.body,
		redirect: 'manual',
	});
	const responseHeaders = copyResponseHeaders(upstream.headers);
	const location = responseHeaders.get('location');
	if (location) {
		const redirect = new URL(location, backend);
		responseHeaders.set(
			'location',
			`${incoming.origin}${API_PREFIX}${redirect.pathname}${redirect.search}${redirect.hash}`,
		);
	}
	return new Response(upstream.body, {
		status: upstream.status,
		statusText: upstream.statusText,
		headers: responseHeaders,
	});
}

export default {
	async fetch(request, env) {
		const { pathname } = new URL(request.url);
		if (pathname === API_PREFIX || pathname.startsWith(`${API_PREFIX}/`)) {
			return proxyApi(request, env);
		}
		return env.ASSETS.fetch(request);
	},
};
