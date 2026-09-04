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

/** ECharts-Option für den Profitabilitäts-Gauge. Wert/Label/Status liegen außerhalb als HTML. */
export function buildProfitabilityGaugeOption(
  valuePercent: number | null | undefined,
): EChartsCoreOption | null {
  const state = getGaugeState(valuePercent);
  if (!state.isAvailable) return null;

  const clamped = sanitizeNumber(state.clampedValue);
  const criticalRatio = GAUGE_ZONE_CRITICAL_MAX / GAUGE_SCALE_MAX;
  const watchRatio = GAUGE_ZONE_WATCH_MAX / GAUGE_SCALE_MAX;

  return {
    animationDuration: 300,
    series: [
      {
        type: "gauge",
        startAngle: 180,
        endAngle: 0,
        center: ["50%", "72%"],
        radius: "95%",
        min: 0,
        max: GAUGE_SCALE_MAX,
        splitNumber: 5,
        axisLine: {
          lineStyle: {
            width: 18,
            color: [
              [criticalRatio, GAUGE_COLOR_CRITICAL],
              [watchRatio, GAUGE_COLOR_WATCH],
              [1, GAUGE_COLOR_POSITIVE],
            ],
          },
        },
        pointer: {
          icon: "path://M2.9,0.7L2.9,0.7c1.4,0,2.6,1.2,2.6,2.6v19.8c0,1.4-1.2,2.6-2.6,2.6l0,0c-1.4,0-2.6-1.2-2.6-2.6V3.3C0.3,1.9,1.4,0.7,2.9,0.7z",
          length: "62%",
          width: 6,
          offsetCenter: [0, 0],
          itemStyle: { color: "#0f172a" },
        },
        anchor: {
          show: true,
          showAbove: true,
          size: 12,
          itemStyle: { color: "#0f172a", borderWidth: 2, borderColor: "#f8fafc" },
        },
        axisTick: { show: false },
        splitLine: {
          length: 10,
          distance: -22,
          lineStyle: { width: 2, color: "#1e293b" },
        },
        axisLabel: {
          distance: -36,
          color: "#64748b",
          fontSize: 11,
          formatter: (value: number) => {
            const marks = [0, GAUGE_ZONE_CRITICAL_MAX, GAUGE_ZONE_WATCH_MAX, GAUGE_SCALE_MAX];
            return marks.includes(value) ? `${value}` : "";
          },
        },
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
    animationDuration: 300,
    grid: { left: 56, right: 12, top: 16, bottom: 28 },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
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
            borderRadius: [6, 6, 0, 0],
          },
        })),
        barMaxWidth: 40,
      },
    ],
  };
}
