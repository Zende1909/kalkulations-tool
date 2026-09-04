/** Gauge-Zustandslogik für EBIT-/ROI-Tachometer. */

export const GAUGE_SCALE_MIN = 0;
/** Untere Referenzskala / Zonenende „positiv“. */
export const GAUGE_SCALE_MAX = 25;
export const GAUGE_ZONE_CRITICAL_MAX = 5;
export const GAUGE_ZONE_WATCH_MAX = 9;
export const GAUGE_COLOR_OVER_SCALE = "#334155";

export const GAUGE_COLOR_CRITICAL = "#DC2626";
export const GAUGE_COLOR_WATCH = "#D97706";
export const GAUGE_COLOR_POSITIVE = "#16A34A";

/** Inset der HTML-Skalenmarken relativ zur Chartbreite (passend zu ECharts radius). */
export const GAUGE_SCALE_LABEL_INSET_PERCENT = 8;

export type GaugeZone = "critical" | "watch" | "positive" | "unavailable";

export interface GaugeState {
  actualValue: number | null;
  /** Zeigerwert auf der dargestellten Skala (0 … scaleMax). */
  clampedValue: number;
  /** Obere Skalengrenze der Darstellung (≥ 25, bei hohen Werten erweitert). */
  scaleMax: number;
  scaleMarks: number[];
  needleAngle: number;
  zone: GaugeZone;
  zoneLabel: string;
  zoneColor: string;
  isBelowScale: boolean;
  /** Wert liegt über der 25-%-Referenzzone (nicht zwingend über scaleMax). */
  isAboveScale: boolean;
  isAvailable: boolean;
}

/** Obere Skalengrenze: mindestens 25 %, sonst aufgerundet damit der Zeiger den echten Wert zeigt. */
export function niceGaugeScaleMax(actualValue: number): number {
  if (!Number.isFinite(actualValue) || actualValue <= GAUGE_SCALE_MAX) {
    return GAUGE_SCALE_MAX;
  }
  const step = actualValue <= 50 ? 5 : 10;
  return Math.max(GAUGE_SCALE_MAX, Math.ceil(actualValue / step) * step);
}

export function buildGaugeScaleMarks(scaleMax: number): number[] {
  const marks = [
    GAUGE_SCALE_MIN,
    GAUGE_ZONE_CRITICAL_MAX,
    GAUGE_ZONE_WATCH_MAX,
    GAUGE_SCALE_MAX,
  ];
  if (scaleMax > GAUGE_SCALE_MAX) {
    marks.push(scaleMax);
  }
  return marks;
}

/** Horizontale Position einer Skalenmarke entlang der Halbkreis-Basis (0–100 % der Arc-Breite). */
export function gaugeScaleMarkLeftPercent(mark: number, scaleMax = GAUGE_SCALE_MAX): number {
  const max = scaleMax > 0 ? scaleMax : GAUGE_SCALE_MAX;
  const clamped = Math.min(Math.max(mark, GAUGE_SCALE_MIN), max);
  return (clamped / max) * 100;
}

/** Halbkreis: 180° (links, 0 %) → 0° (rechts, scaleMax). */
export function valueToNeedleAngle(clampedPercent: number, scaleMax = GAUGE_SCALE_MAX): number {
  const max = scaleMax > 0 ? scaleMax : GAUGE_SCALE_MAX;
  const ratio =
    Math.min(Math.max(clampedPercent, GAUGE_SCALE_MIN), max) / max;
  const angle = 180 - ratio * 180;
  return Number.isFinite(angle) ? angle : 180;
}

export function getGaugeState(valuePercent: number | null | undefined): GaugeState {
  if (valuePercent == null || !Number.isFinite(valuePercent)) {
    return {
      actualValue: null,
      clampedValue: GAUGE_SCALE_MIN,
      scaleMax: GAUGE_SCALE_MAX,
      scaleMarks: buildGaugeScaleMarks(GAUGE_SCALE_MAX),
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
  const scaleMax = niceGaugeScaleMax(actualValue);
  const isBelowScale = actualValue < GAUGE_SCALE_MIN;
  const isAboveScale = actualValue > GAUGE_SCALE_MAX;
  const clampedValue = Math.min(Math.max(actualValue, GAUGE_SCALE_MIN), scaleMax);

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
    scaleMax,
    scaleMarks: buildGaugeScaleMarks(scaleMax),
    needleAngle: valueToNeedleAngle(clampedValue, scaleMax),
    zone,
    zoneLabel,
    zoneColor,
    isBelowScale,
    isAboveScale,
    isAvailable: true,
  };
}
