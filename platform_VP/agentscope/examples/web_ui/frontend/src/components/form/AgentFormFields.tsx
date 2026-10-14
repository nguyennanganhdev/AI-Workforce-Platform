import { useTranslation } from 'react-i18next';

import type { AgentSchemaV2Response, JSONSchema } from '@/api';
import { NESTED_SECTIONS, sliceSchema } from '@/components/form/agent-form-utils';
import { SchemaForm, type SchemaFormValue } from '@/components/form/SchemaForm';
import {
	FieldDescription,
	FieldGroup,
	FieldLegend,
	FieldSeparator,
	FieldSet,
} from '@/components/ui/field';

export type AgentSection = 'identity' | 'context_config' | 'react_config' | 'invite_config';

export type AgentFormValues = {
	[K in AgentSection]: Record<string, SchemaFormValue>;
};

interface Props {
	schema: AgentSchemaV2Response;
	values: AgentFormValues;
	onChange: (section: AgentSection, key: string, value: SchemaFormValue) => void;
}

const IDENTITY_I18N = 'identity';

const toKebab = (s: string) => s.replace(/_/g, '-');

export function AgentFormFields({ schema, values, onChange }: Props) {
	const { t } = useTranslation();
	const sections = sliceSchema(schema.schema);

	const rows: Array<{ key: AgentSection; i18n: string; sectionSchema: JSONSchema }> = [
		{ key: 'identity', i18n: IDENTITY_I18N, sectionSchema: sections.identity },
		...NESTED_SECTIONS.map((s) => ({
			key: s.key as AgentSection,
			i18n: s.i18n,
			sectionSchema: sections[s.key],
		})),
	];

	return (
		<FieldGroup>
			{rows.map(({ key: sectionKey, i18n: sectionI18n, sectionSchema }, idx) => {
				const legend = t(`agent-form.${sectionI18n}.legend`, {
					defaultValue: sectionSchema.title ?? sectionKey,
				});
				const description = t(`agent-form.${sectionI18n}.description`, {
					defaultValue: '',
				});
				return (
					<div key={sectionKey}>
						{idx > 0 && <FieldSeparator className="my-0" />}
						<FieldSet>
							<FieldLegend>{legend}</FieldLegend>
							{description && <FieldDescription>{description}</FieldDescription>}
							<SchemaForm
								schema={sectionSchema}
								values={values[sectionKey]}
								onChange={(k, v) => onChange(sectionKey, k, v)}
								idPrefix={`agent-form-${sectionI18n}`}
								labelFor={(k, prop) =>
									t(`agent-form.${sectionI18n}.${toKebab(k)}.label`, {
										defaultValue: prop.title ?? k.replace(/_/g, ' '),
									})
								}
								placeholderFor={(k, prop) =>
									t(`agent-form.${sectionI18n}.${toKebab(k)}.placeholder`, {
										defaultValue: prop.description ?? '',
									}) || undefined
								}
								// Only for fields whose label cannot carry the
								// whole story on its own — hence no fallback to
								// `prop.description`, which is English-only and
								// already serves as the placeholder.
								descriptionFor={(k) =>
									t(`agent-form.${sectionI18n}.${toKebab(k)}.description`, {
										defaultValue: '',
									}) || undefined
								}
							/>
						</FieldSet>
					</div>
				);
			})}
		</FieldGroup>
	);
}
