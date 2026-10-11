import { ChevronRight } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import type { AgentSchemaV2Response, JSONSchema, JSONSchemaProperty } from '@/api';
import { SchemaForm, type SchemaFormValue } from '@/components/form/SchemaForm';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
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

/**
 * Section derivation from the flat `AgentData` schema. Ordered — controls
 * the visual order of the fieldsets. "identity" carries every top-level
 * property that is NOT one of the nested-object sections below, so any
 * newly added scalar / boolean / textarea field on `AgentData` shows up
 * in the identity fieldset automatically.
 */
const NESTED_SECTIONS: Array<{ key: Exclude<AgentSection, 'identity'>; i18n: string }> = [
	{ key: 'context_config', i18n: 'context-config' },
	{ key: 'react_config', i18n: 'react-config' },
	{ key: 'invite_config', i18n: 'invite-config' },
];

const IDENTITY_I18N = 'identity';

const toKebab = (s: string) => s.replace(/_/g, '-');

/** Split the flat `AgentData` schema into the sections the form renders
 * (currently four: `identity` + one per `NESTED_SECTIONS` entry). */
function sliceSchema(root: JSONSchema): Record<AgentSection, JSONSchema> {
	const props = root.properties ?? {};
	const nestedKeys = new Set(NESTED_SECTIONS.map((s) => s.key));

	const identityProps: Record<string, JSONSchemaProperty> = {};
	for (const [k, prop] of Object.entries(props)) {
		if (nestedKeys.has(k as Exclude<AgentSection, 'identity'>)) continue;
		identityProps[k] = prop;
	}

	const identity: JSONSchema = {
		type: 'object',
		title: 'Identity',
		properties: identityProps,
		required: (root.required ?? []).filter(
			(r) => !nestedKeys.has(r as Exclude<AgentSection, 'identity'>),
		),
	};

	return {
		identity,
		context_config: (props.context_config as JSONSchema) ?? {
			type: 'object',
			properties: {},
		},
		react_config: (props.react_config as JSONSchema) ?? {
			type: 'object',
			properties: {},
		},
		invite_config: (props.invite_config as JSONSchema) ?? {
			type: 'object',
			properties: {},
		},
	};
}

/**
 * The agent form: who the agent is, then everything else.
 *
 * Only the identity fields are on show. The context, ReAct and invite sections
 * all have working defaults and most agents never change them, so each sits
 * behind its own disclosure — otherwise the first thing a new agent's author
 * meets is three ratios and a forty-line compression prompt.
 */
export function AgentFormFields({ schema, values, onChange }: Props) {
	const { t } = useTranslation();
	const sections = sliceSchema(schema.schema);

	const form = (sectionKey: AgentSection, sectionI18n: string) => (
		<SchemaForm
			schema={sections[sectionKey]}
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
			// Only for fields whose label cannot carry the whole story on
			// its own — hence no fallback to `prop.description`, which is
			// English-only and already serves as the placeholder.
			descriptionFor={(k) =>
				t(`agent-form.${sectionI18n}.${toKebab(k)}.description`, {
					defaultValue: '',
				}) || undefined
			}
		/>
	);

	return (
		<FieldGroup>
			<FieldSet>
				{/* The dialog's own title and description already say this. */}
				<FieldLegend className="sr-only">
					{t(`agent-form.${IDENTITY_I18N}.legend`)}
				</FieldLegend>
				{form('identity', IDENTITY_I18N)}
			</FieldSet>
			<FieldSeparator className="my-0" />
			<FieldSet>
				<FieldLegend>{t('agent-form.advanced.legend')}</FieldLegend>
				<FieldDescription>{t('agent-form.advanced.description')}</FieldDescription>
				<div className="flex flex-col gap-2">
					{NESTED_SECTIONS.map(({ key, i18n }) => {
						const description = t(`agent-form.${i18n}.description`, {
							defaultValue: '',
						});
						return (
							<Collapsible key={key} className="rounded-lg border bg-card">
								<CollapsibleTrigger asChild>
									<button
										type="button"
										className="group flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left hover:bg-muted/60"
									>
										<span className="min-w-0 flex-1">
											<span className="block text-sm font-medium">
												{t(`agent-form.${i18n}.legend`, {
													defaultValue: sections[key].title ?? key,
												})}
											</span>
											{description && (
												<span className="block text-xs text-muted-foreground">
													{description}
												</span>
											)}
										</span>
										<ChevronRight className="size-4 shrink-0 text-muted-foreground transition-transform group-data-[state=open]:rotate-90" />
									</button>
								</CollapsibleTrigger>
								<CollapsibleContent className="border-t px-3 py-3">
									{form(key, i18n)}
								</CollapsibleContent>
							</Collapsible>
						);
					})}
				</div>
			</FieldSet>
		</FieldGroup>
	);
}

/** Build a fresh `AgentFormValues` populated from each section schema's defaults. */
export function defaultAgentFormValues(schema: AgentSchemaV2Response): AgentFormValues {
	const sections = sliceSchema(schema.schema);
	const fromDefaults = (section: JSONSchema): Record<string, SchemaFormValue> => {
		const out: Record<string, SchemaFormValue> = {};
		for (const [k, prop] of Object.entries(section.properties ?? {})) {
			if (prop.const !== undefined) continue;
			if (prop.default !== undefined) out[k] = prop.default as SchemaFormValue;
		}
		return out;
	};
	return {
		identity: fromDefaults(sections.identity),
		context_config: fromDefaults(sections.context_config),
		react_config: fromDefaults(sections.react_config),
		invite_config: fromDefaults(sections.invite_config),
	};
}
