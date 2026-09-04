/** Gauge-Zustandslogik für EBIT-/ROI-Tachometer (feste Skala 0–25 %). */

export const GAUGE_SCALE_MIN = 0;
export const GAUGE_SCALE_MAX = 25;
export const GAUGE_ZONE_CRITICAL_MAX = 5;
export const GAUGE_ZONE_WATCH_MAX = 9;
export const GAUGE_COLOR_OVER_SCALE = "#334155";

export const GAUGE_COLOR_CRITICAL = "#DC2626";
export const GAUGE_COLOR_WATCH = "#D97706";
export const GAUGE_COLOR_POSITIVE = "#16A34A";

/** Inset der HTML-Skalenmarken relativ zur Chartbreite (passend zu ECharts radius). */
export const GAUGE_SCALE_LABEL_INSET_PERCENT = 8;

/** Sichtbare Skalenmarken unterhalb der Gauge-Geometrie. */
export const GAUGE_SCALE_MARKS = [
  GAUGE_SCALE_MIN,
  GAUGE_ZONE_CRITICAL_MAX,
  GAUGE_ZONE_WATCH_MAX,
  GAUGE_SCALE_MAX,
] as const;

export type GaugeZone = "critical" | "watch" | "positive" | "unavailable";

export interface GaugeState {
  actualValue: number | null;
  /** Zeigerwert auf der Skala 0–25 (geclampte Darstellung). */
  clampedValue: number;
  scaleMax: number;
  scaleMarks: number[];
  needleAngle: number;
  zone: GaugeZone;
  zoneLabel: string;
  zoneColor: string;
  isBelowScale: boolean;
  isAboveScale: boolean;
  isAvailable: boolean;
}

/** Horizontale Position einer Skalenmarke entlang der Halbkreis-Basis (0–100 %). */
export function gaugeScaleMarkLeftPercent(mark: number): number {
  const clamped = Math.min(Math.max(mark, GAUGE_SCALE_MIN), GAUGE_SCALE_MAX);
  return (clamped / GAUGE_SCALE_MAX) * 100;
}

/** Halbkreis: 180° (links, 0 %) → 0° (rechts, 25 %). */
export function valueToNeedleAngle(clampedPercent: number): number {
  const ratio =
    Math.min(Math.max(clampedPercent, GAUGE_SCALE_MIN), GAUGE_SCALE_MAX) /
    GAUGE_SCALE_MAX;
  const angle = 180 - ratio * 180;
  return Number.isFinite(angle) ? angle : 180;
}

export function getGaugeState(valuePercent: number | null | undefined): GaugeState {
  if (valuePercent == null || !Number.isFinite(valuePercent)) {
    return {
      actualValue: null,
      clampedValue: GAUGE_SCALE_MIN,
      scaleMax: GAUGE_SCALE_MAX,
      scaleMarks: [...GAUGE_SCALE_MARKS],
      needleAngle: 180,
      zone: "unavailable",
      zoneLabel: "nicht verfügbar",
      zoneColor: "#64748b",
      isBelowScale: false,
      isAboveScale: false,
      isAvailable: false,
    };
  }

  const actualValue = valuePercent;
  const isBelowScale = actualValue < GAUGE_SCALE_MIN;
  const isAboveScale = actualValue > GAUGE_SCALE_MAX;
  const clampedValue = Math.min(
    Math.max(actualValue, GAUGE_SCALE_MIN),
    GAUGE_SCALE_MAX,
  );

  let zone: GaugeZone;
  let zoneLabel: string;
  let zoneColor: string;

  if (isBelowScale) {
    zone = "critical";
    zoneLabel = "negativ";
    zoneColor = GAUGE_COLOR_CRITICAL;
  } else if (isAboveScale) {
    zone = "positive";
    zoneLabel = "über Skala";
    zoneColor = GAUGE_COLOR_OVER_SCALE;
  } else if (actualValue < GAUGE_ZONE_CRITICAL_MAX) {
    zone = "critical";
    zoneLabel = "kritisch";
    zoneColor = GAUGE_COLOR_CRITICAL;
  } else if (actualValue < GAUGE_ZONE_WATCH_MAX) {
    zone = "watch";
    zoneLabel = "beobachten";
    zoneColor = GAUGE_COLOR_WATCH;
  } else {
    zone = "positive";
    zoneLabel = "positiv";
    zoneColor = GAUGE_COLOR_POSITIVE;
  }

  return {
    actualValue,
    clampedValue,
    scaleMax: GAUGE_SCALE_MAX,
    scaleMarks: [...GAUGE_SCALE_MARKS],
    needleAngle: valueToNeedleAngle(clampedValue),
    zone,
    zoneLabel,
    zoneColor,
    isBelowScale,
    isAboveScale,
    isAvailable: true,
  };
}
