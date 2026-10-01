/**
 * What each measured quantity is expressed in, and what an ordinary value of it looks like.
 *
 * A reading is only as good as its unit. A surface moisture of "24" means one thing in percent and
 * nothing at all in degrees, and a tool that passed it on without checking would hand the agent a
 * number it could reason from.
 *
 * - `units` maps every accepted unit to the factor that converts it to `canonicalUnit`. Reading, a
 *   unit outside it marks the reading `bad`; recording, it refuses the measurement.
 * - `expectedRange` is what an ordinary value falls in, in the canonical unit. A value outside it
 *   is still recorded, and flagged, because an extreme measurement is exactly the one a person on
 *   duty needs to see.
 *
 * Deliberately short, and the ranges are working values rather than approved limits: general.md
 * §14 leaves which metrics the demo includes, and what counts as normal for each, to the Domain
 * Owner.
 */
export type MetricDefinition = {
  metric: string;
  canonicalUnit: string;
  units: Readonly<Record<string, number>>;
  expectedRange: { min: number; max: number };
};

export const METRICS: readonly MetricDefinition[] = [
  {
    metric: "condensate_level",
    canonicalUnit: "mm",
    units: { mm: 1, cm: 10 },
    expectedRange: { min: 0, max: 15 },
  },
  {
    metric: "outlet_temperature",
    canonicalUnit: "C",
    units: { C: 1, "°C": 1 },
    expectedRange: { min: 35, max: 75 },
  },
  {
    metric: "leakage_current",
    canonicalUnit: "mA",
    units: { mA: 1, A: 1000 },
    // A residual-current device trips at 30 mA; anything above it is not ordinary.
    expectedRange: { min: 0, max: 30 },
  },
  {
    metric: "surface_moisture",
    canonicalUnit: "%",
    units: { "%": 1 },
    expectedRange: { min: 0, max: 20 },
  },
  {
    metric: "flow_rate",
    canonicalUnit: "L/min",
    units: { "L/min": 1, "l/min": 1 },
    expectedRange: { min: 0.5, max: 20 },
  },
  {
    metric: "drain_flow",
    canonicalUnit: "L/min",
    units: { "L/min": 1, "l/min": 1 },
    expectedRange: { min: 0.5, max: 10 },
  },
  {
    metric: "supply_pressure",
    canonicalUnit: "bar",
    units: { bar: 1, kPa: 0.01 },
    expectedRange: { min: 1.5, max: 6 },
  },
  {
    metric: "crack_width",
    canonicalUnit: "mm",
    units: { mm: 1 },
    expectedRange: { min: 0, max: 0.3 },
  },
  {
    metric: "door_gap",
    canonicalUnit: "mm",
    units: { mm: 1 },
    expectedRange: { min: 0, max: 3 },
  },
];

export function metricDefinition(metric: string): MetricDefinition | undefined {
  return METRICS.find((candidate) => candidate.metric === metric);
}

/**
 * Whether `unit` is an accepted unit for `metric`.
 *
 * `undefined` for a metric this list does not know, which is a different answer from `false`: there
 * is no rule to break, so a reader leaves the reading's quality as the source gave it.
 */
export function unitAccepted(
  metric: string,
  unit: string,
): boolean | undefined {
  const definition = metricDefinition(metric);
  return definition ? Object.hasOwn(definition.units, unit) : undefined;
}
