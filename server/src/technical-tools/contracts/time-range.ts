import { z } from "zod";

/**
 * A window of time, `[from, to)`, as every tool that takes one accepts it.
 *
 * One definition so the tools cannot disagree about what a valid window is. A window that ends
 * where it begins, or before, is refused on `time_range` itself rather than on one of its ends:
 * neither end is wrong on its own, only the pair.
 */
export const timeRangeSchema = z
  .strictObject({
    from: z.iso.datetime({ offset: true }),
    to: z.iso.datetime({ offset: true }),
  })
  .refine((range) => Date.parse(range.from) < Date.parse(range.to), {
    message: "time_range.from must be earlier than time_range.to.",
  });

export type TimeRange = z.infer<typeof timeRangeSchema>;
