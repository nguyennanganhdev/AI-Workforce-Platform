// HTTP deployments still expose getRandomValues, but randomUUID requires a
// secure context. Install before the app so the message SDK can use it too.
if (typeof globalThis.crypto.randomUUID !== 'function') {
	globalThis.crypto.randomUUID = () => {
		const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16));
		bytes[6] = (bytes[6] & 0x0f) | 0x40;
		bytes[8] = (bytes[8] & 0x3f) | 0x80;
		const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0'));
		return `${hex.slice(0, 4).join('')}-${hex.slice(4, 6).join('')}-${hex.slice(6, 8).join('')}-${hex.slice(8, 10).join('')}-${hex.slice(10).join('')}`;
	};
}
