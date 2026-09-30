import { z } from "zod";

/**
 * `asset.read` (tools.md §3.2).
 *
 * `building_id` is required and one of `asset_id` or `location` must be given: a call naming
 * neither would ask for every asset in the building, which is a listing rather than a lookup and
 * is how a tool ends up picking one on the agent's behalf.
 */
export const assetReadInputSchema = z
  .strictObject({
    building_id: z.uuid(),
    asset_id: z.string().min(1).optional(),
    location: z.string().min(2).max(500).optional(),
    asset_type: z.string().max(100).optional(),
  })
  .refine((input) => Boolean(input.asset_id) || Boolean(input.location), {
    path: ["asset_id"],
    message: "Either asset_id or location is required.",
  });

export type AssetReadInput = z.infer<typeof assetReadInputSchema>;

export const assetSchema = z.strictObject({
  asset_id: z.string(),
  type: z.string(),
  model: z.string().nullable(),
  location: z.string(),
  ownership: z.string().nullable(),
  warranty_until: z.string().nullable(),
  status: z.string(),
  updated_at: z.iso.datetime({ offset: true }),
});

export const assetReadOutputSchema = z.strictObject({
  assets: z.array(assetSchema),
});

export type AssetReadOutput = z.infer<typeof assetReadOutputSchema>;
