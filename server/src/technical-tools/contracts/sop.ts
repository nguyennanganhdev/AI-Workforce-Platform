import { z } from "zod";
import { ISSUE_CODE_PATTERN } from "../reference/issue-codes";

/** `sop_kb.retrieve` (tools.md §3.1). */
export const sopRetrieveInputSchema = z.strictObject({
  building_id: z.uuid(),
  issue_code: z.string().regex(ISSUE_CODE_PATTERN),
  query: z.string().min(3).max(1000),
  effective_at: z.iso.datetime({ offset: true }).optional(),
  language: z.string().default("vi"),
  limit: z.number().int().min(1).max(20).default(5),
});

export type SopRetrieveInput = z.infer<typeof sopRetrieveInputSchema>;

export const sopDocumentSchema = z.strictObject({
  document_id: z.uuid(),
  code: z.string(),
  title: z.string(),
  version_no: z.number().int().min(1),
  effective_from: z.iso.datetime({ offset: true }),
  effective_to: z.iso.datetime({ offset: true }).nullable(),
  excerpt: z.string(),
  acceptance_criteria: z.array(z.string()),
  source_refs: z.array(z.string()),
});

export const sopRetrieveOutputSchema = z.strictObject({
  documents: z.array(sopDocumentSchema),
});

export type SopRetrieveOutput = z.infer<typeof sopRetrieveOutputSchema>;
