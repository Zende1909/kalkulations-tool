import { useEffect, useRef, type CSSProperties } from "react";
import * as echarts from "echarts/core";
import type { EChartsCoreOption, EChartsType } from "echarts/core";
import { BarChart, GaugeChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([BarChart, GaugeChart, GridComponent, TooltipComponent, CanvasRenderer]);

function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Robustes ECharts-Lifecycle-Management für React. */
export function useEcharts(
  option: EChartsCoreOption | null,
  opts: { className?: string; style?: CSSProperties; "aria-hidden"?: boolean } = {},
) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<EChartsType | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const chart = echarts.init(el, undefined, { renderer: "canvas" });
    chartRef.current = chart;

    const observer = new ResizeObserver(() => {
      chart.resize();
    });
    observer.observe(el);

    return () => {
      observer.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || option == null) return;
    const reduced = prefersReducedMotion();
    chart.setOption(
      {
        ...option,
        animation: reduced ? false : option.animation !== false,
      },
      { notMerge: true },
    );
  }, [option]);

  return {
    containerRef,
    containerProps: {
      ref: containerRef,
      className: opts.className,
      style: opts.style,
      "aria-hidden": opts["aria-hidden"],
    } as const,
  };
}

export { echarts };
export type { EChartsCoreOption };
