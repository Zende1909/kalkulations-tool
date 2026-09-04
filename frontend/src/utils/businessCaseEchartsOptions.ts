import type { EChartsCoreOption } from "echarts/core";

import {
  GAUGE_COLOR_CRITICAL,
  GAUGE_COLOR_POSITIVE,
  GAUGE_COLOR_WATCH,
  GAUGE_SCALE_MAX,
  GAUGE_ZONE_CRITICAL_MAX,
  GAUGE_ZONE_WATCH_MAX,
  getGaugeState,
} from "./businessCaseGauge";
import {
  type RevenueChartPoint,
  type RevenueCurrencyScale,
  formatRevenueOnScale,
} from "./businessCaseRevenueChart";

function sanitizeNumber(value: number): number {
  return Number.isFinite(value) ? value : 0;
}

/**
 * ECharts-Option nur für Gauge-Geometrie:
 * Farbzonen, Zeiger, Anker. Kein title/detail/axisLabel.
 * Prozentwert, Label und Status liegen außerhalb als HTML.
 */
export function buildProfitabilityGaugeOption(
  valuePercent: number | null | undefined,
): EChartsCoreOption | null {
  const state = getGaugeState(valuePercent);
  if (!state.isAvailable) return null;

  const clamped = sanitizeNumber(state.clampedValue);
  const criticalRatio = GAUGE_ZONE_CRITICAL_MAX / GAUGE_SCALE_MAX;
  const watchRatio = GAUGE_ZONE_WATCH_MAX / GAUGE_SCALE_MAX;

  return {
    animationDuration: 280,
    series: [
      {
        type: "gauge",
        startAngle: 180,
        endAngle: 0,
        // Halbkreis sitzt unten im Container; Text liegt darunter im HTML.
        center: ["50%", "100%"],
        radius: "100%",
        min: 0,
        max: GAUGE_SCALE_MAX,
        splitNumber: 1,
        axisLine: {
          roundCap: true,
          lineStyle: {
            width: 14,
            color: [
              [criticalRatio, GAUGE_COLOR_CRITICAL],
              [watchRatio, GAUGE_COLOR_WATCH],
              [1, GAUGE_COLOR_POSITIVE],
            ],
          },
        },
        pointer: {
          icon: "path://M2.9,0.7L2.9,0.7c1.4,0,2.6,1.2,2.6,2.6v19.8c0,1.4-1.2,2.6-2.6,2.6l0,0c-1.4,0-2.6-1.2-2.6-2.6V3.3C0.3,1.9,1.4,0.7,2.9,0.7z",
          length: "68%",
          width: 5,
          offsetCenter: [0, 0],
          itemStyle: { color: "#0f172a" },
        },
        anchor: {
          show: true,
          showAbove: true,
          size: 10,
          itemStyle: { color: "#0f172a", borderWidth: 2, borderColor: "#ffffff" },
        },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        title: { show: false },
        detail: { show: false },
        data: [{ value: clamped }],
      },
    ],
  };
}

export function sanitizeChartNumber(value: number | null | undefined, fallback = 0): number {
  if (value == null || !Number.isFinite(value)) return fallback;
  return value;
}

export function buildRevenueBarOption(
  points: RevenueChartPoint[],
  scale: RevenueCurrencyScale,
  seriesLabel: string,
): EChartsCoreOption {
  const years = points.map((p) => String(p.calendar_year));
  const values = points.map((p) => sanitizeChartNumber(p.display_revenue, 0));
  const lastIndex = values.length - 1;

  return {
    animationDuration: 280,
    grid: { left: 52, right: 8, top: 12, bottom: 24 },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      show: true,
      alwaysShowContent: false,
      formatter: (params: unknown) => {
        const item = Array.isArray(params) ? params[0] : params;
        if (!item || typeof item !== "object") return "";
        const entry = item as { name?: string | number; value?: number | string };
        const year = String(entry.name ?? "");
        const raw = typeof entry.value === "number" ? entry.value : Number(entry.value);
        return `Jahr ${year}<br/>Umsatz (${seriesLabel}): ${formatRevenueOnScale(
          Number.isFinite(raw) ? raw : null,
          scale,
        )}`;
      },
    },
    xAxis: {
      type: "category",
      data: years,
      axisTick: { show: false },
      axisLine: { show: false },
      axisLabel: { color: "#475569", fontSize: 11 },
    },
    yAxis: {
      type: "value",
      min: 0,
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { type: "dashed", color: "#e2e8f0" } },
      axisLabel: {
        color: "#64748b",
        fontSize: 10,
        formatter: (value: number) =>
          formatRevenueOnScale(sanitizeChartNumber(value), scale, { compact: true }),
      },
    },
    series: [
      {
        type: "bar",
        name: "Umsatz",
        data: values.map((v, index) => ({
          value: v,
          itemStyle: {
            color: index === lastIndex ? "#1d4ed8" : "#3b82f6",
            borderRadius: [4, 4, 0, 0],
          },
        })),
        barMaxWidth: 36,
      },
    ],
  };
}
