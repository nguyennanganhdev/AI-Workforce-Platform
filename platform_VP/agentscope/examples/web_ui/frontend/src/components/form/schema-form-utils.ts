import type { JSONSchema } from '@/api';
import type { SchemaFormValue } from '@/components/form/SchemaForm';

export const DEFAULT_SKIP_FIELDS = new Set(['id', 'type']);

/** Extract initial values from a JSON Schema's `default` fields. */
export function defaultValuesFromSchema(
	schema: JSONSchema,
	skipFields: ReadonlySet<string> = DEFAULT_SKIP_FIELDS,
): Record<string, SchemaFormValue> {
	const out: Record<string, SchemaFormValue> = {};
	for (const [key, prop] of Object.entries(schema.properties ?? {})) {
		if (skipFields.has(key) || prop.const !== undefined) continue;
		if (prop.default !== undefined) {
			out[key] = prop.default as SchemaFormValue;
		}
	}
	return out;
}
