// Mirrors LEGACY_MAPE_IMPLAUSIBLE in backend/app/services/metric_registry.py: a recorded percentage error above this was decided by
// near-zero actual values, not by forecast quality, so it is never shown as a number.
export const LEGACY_MAPE_IMPLAUSIBLE = 1000;

/** The percentage error to show, or null when it is missing, not finite, negative or implausibly large. Never NaN/Infinity text. */
export function displayMape(value: unknown): number | null {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > LEGACY_MAPE_IMPLAUSIBLE) return null;
  return value;
}
