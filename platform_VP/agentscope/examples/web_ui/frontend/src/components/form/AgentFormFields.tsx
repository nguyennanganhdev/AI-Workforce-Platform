import { ChevronRight } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import type { AgentSchemaV2Response } from '@/api';
import { NESTED_SECTIONS, sliceSchema } from '@/components/form/agent-form-utils';
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
	governedPrompt?: boolean;
	schema: AgentSchemaV2Response;
	values: AgentFormValues;
	onChange: (section: AgentSection, key: string, value: SchemaFormValue) => void;
}

const IDENTITY_I18N = 'identity';

const toKebab = (s: string) => s.replace(/_/g, '-');

/**
 * The agent form: who the agent is, then everything else.
 *
 * Only the identity fields are on show. The context, ReAct and invite sections
 * all have working defaults and most agents never change them, so each sits
 * behind its own disclosure — otherwise the first thing a new agent's author
 * meets is three ratios and a forty-line compression prompt.
 */
export function AgentFormFields({ schema, values, onChange, governedPrompt = false }: Props) {
	const { t } = useTranslation();
	const sections = sliceSchema(schema.schema);

	const form = (sectionKey: AgentSection, sectionI18n: string) => (
		<SchemaForm
			schema={sections[sectionKey]}
			values={values[sectionKey]}
			skipFields={governedPrompt && sectionKey === 'identity' ? new Set(['id', 'type', 'system_prompt']) : undefined}
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
				{governedPrompt && <FieldDescription>{t('agentManagement.governedPrompt')}</FieldDescription>}
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
