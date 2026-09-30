/**
 * What each measured quantity is expressed in.
 *
 * A reading is only as good as its unit. A surface moisture of "24" means one thing in percent and
 * nothing at all in degrees, and a tool that reported it without checking would hand the agent a
 * number it could reason from. `sensor.read` marks a reading whose unit is not accepted here as
 * `bad` rather than converting or dropping it: the value is still shown, and nobody concludes
 * anything from it.
 *
 * Deliberately short. It holds the metrics the technical flows use, and general.md §14 leaves which
 * sensors and metrics the demo includes to the Domain Owner. A metric not listed is not refused; its
 * unit is simply not checked, because there is nothing to check it against.
 */
export type MetricDefinition = {
  metric: string;
  canonicalUnit: string;
  acceptedUnits: readonly string[];
};

export const METRICS: readonly MetricDefinition[] = [
  { metric: "condensate_level", canonicalUnit: "mm", acceptedUnits: ["mm"] },
  {
    metric: "outlet_temperature",
    canonicalUnit: "C",
    acceptedUnits: ["C", "°C"],
  },
  { metric: "leakage_current", canonicalUnit: "mA", acceptedUnits: ["mA"] },
  { metric: "surface_moisture", canonicalUnit: "%", acceptedUnits: ["%"] },
  {
    metric: "flow_rate",
    canonicalUnit: "L/min",
    acceptedUnits: ["L/min", "l/min"],
  },
  {
    metric: "drain_flow",
    canonicalUnit: "L/min",
    acceptedUnits: ["L/min", "l/min"],
  },
  { metric: "supply_pressure", canonicalUnit: "bar", acceptedUnits: ["bar"] },
  { metric: "crack_width", canonicalUnit: "mm", acceptedUnits: ["mm"] },
  { metric: "door_gap", canonicalUnit: "mm", acceptedUnits: ["mm"] },
];

/**
 * Whether `unit` is an accepted unit for `metric`.
 *
 * `undefined` for a metric this list does not know, which is a different answer from `false`: there
 * is no rule to break, so the caller leaves the reading's quality as the source gave it.
 */
export function unitAccepted(
  metric: string,
  unit: string,
): boolean | undefined {
  const definition = METRICS.find((candidate) => candidate.metric === metric);
  return definition ? definition.acceptedUnits.includes(unit) : undefined;
}
