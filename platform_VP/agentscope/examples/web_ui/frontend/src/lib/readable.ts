/**
 * Helpers that turn runtime text into something a person can read: no agent
 * or session ids, no `name@abcd1234` handles, no raw JSON.
 */

const ID_ARRAY = /\[\s*(?:"[0-9a-f]{24,}"\s*,?\s*)+\]/gi;
const HANDLE_SUFFIX = /@[0-9a-f]{8,}\b/gi;
const HEX_ID = /\b[0-9a-f]{24,}\b/gi;

/** Remove internal ids from a sentence, keeping the words around them. */
export function withoutInternalIds(text: string): string {
	return text
		.replace(ID_ARRAY, '')
		.replace(HANDLE_SUFFIX, '')
		.replace(HEX_ID, '')
		.replace(/\(\s*\)|"\s*"/g, '')
		.replace(/[ \t]{2,}/g, ' ')
		.replace(/\s+([.,;:!?])/g, '$1')
		.trim();
}

/** True when the whole value is an internal id rather than a name. */
export function isInternalId(value: string): boolean {
	return /^[0-9a-f]{24,}$/i.test(value.trim());
}

/** One "label: value" line per field of a JSON object; null when `text` is not one. */
export function readableFields(text: string): Array<[string, string]> | null {
	let value: unknown;
	try {
		value = JSON.parse(text);
	} catch {
		return null;
	}
	if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
	return Object.entries(value as Record<string, unknown>)
		// Identifier fields mean nothing to a person.
		.filter(([key]) => !/(^|_)ids?$/i.test(key))
		.map(([key, field]): [string, string] => [
			key.replace(/_/g, ' '),
			field === null || field === undefined
				? ''
				: typeof field === 'string'
					? withoutInternalIds(field)
					: Array.isArray(field) && field.every((item) => typeof item !== 'object')
						? field.join(', ')
						: typeof field === 'object'
							? Object.entries(field as Record<string, unknown>)
									.map(([name, item]) => `${name.replace(/_/g, ' ')}: ${String(item)}`)
									.join(' · ')
							: String(field),
		])
		.filter(([, text]) => text !== '');
}
