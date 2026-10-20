/**
 * Helpers that turn runtime text into something a person can read: no agent
 * or session ids, no `name@abcd1234` handles, no raw JSON.
 */

// The id patterns also take one space before them, so removal leaves no double space.
const ID_ARRAY = / ?\[\s*(?:"[0-9a-f]{24,}"\s*,?\s*)+\]/gi;
const HANDLE_SUFFIX = /@[0-9a-f]{8,}\b/gi;
const HEX_ID = / ?\b[0-9a-f]{24,}\b/gi;

/**
 * Remove internal ids from text, tidying only the spaces they leave behind,
 * so multi-line output (tables, YAML) keeps its layout.
 */
export function withoutInternalIds(text: string): string {
	return text
		.replace(ID_ARRAY, '')
		.replace(HANDLE_SUFFIX, '')
		.replace(HEX_ID, '')
		.replace(/\(\s*\)|"\s*"/g, '')
		.replace(/ +([.,;:!?])/g, '$1')
		.trim();
}

/** True when the whole value is an internal id rather than a name. */
export function isInternalId(value: string): boolean {
	return /^[0-9a-f]{24,}$/i.test(value.trim());
}

/** A nested value in one line: primitives as is, objects as "key: value · ...". */
function summarise(value: unknown, keepIds: boolean): string {
	if (value === null || value === undefined) return '';
	if (typeof value === 'string') return keepIds ? value : withoutInternalIds(value);
	if (typeof value !== 'object') return String(value);
	if (Array.isArray(value)) return value.map((item) => summarise(item, keepIds)).filter(Boolean).join('; ');
	return Object.entries(value as Record<string, unknown>)
		.filter(([key]) => keepIds || !/(^|_)ids?$/i.test(key))
		.map(([key, item]) => `${key.replace(/_/g, ' ')}: ${summarise(item, keepIds)}`)
		.join(' · ');
}

/**
 * One "label: value" line per field of a JSON object; null when `text` is not
 * one. Identifier fields are hidden unless `keepIds` (approvals must show
 * exactly what an action targets).
 */
export function readableFields(
	text: string,
	{ keepIds = false }: { keepIds?: boolean } = {},
): Array<[string, string]> | null {
	let value: unknown;
	try {
		value = JSON.parse(text);
	} catch {
		return null;
	}
	if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
	return Object.entries(value as Record<string, unknown>)
		// Identifier fields mean nothing to a person reading a result.
		.filter(([key]) => keepIds || !/(^|_)ids?$/i.test(key))
		.map(([key, field]): [string, string] => [key.replace(/_/g, ' '), summarise(field, keepIds)])
		.filter(([, text]) => text !== '');
}
