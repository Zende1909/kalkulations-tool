import { describe, expect, it } from "vitest";

import {
  GAUGE_COLOR_CRITICAL,
  GAUGE_COLOR_POSITIVE,
  GAUGE_COLOR_WATCH,
  GAUGE_SCALE_MAX,
  buildGaugeScaleMarks,
  gaugeScaleMarkLeftPercent,
  getGaugeState,
  niceGaugeScaleMax,
  valueToNeedleAngle,
} from "../utils/businessCaseGauge";
import { formatPercentOrDash } from "../pages/businessCaseFormatting";

describe("getGaugeState", () => {
  it("marks values below 0 % as negativ and clamps needle to 0 %", () => {
    const state = getGaugeState(-3.2);
    expect(state.zone).toBe("critical");
    expect(state.zoneLabel).toBe("negativ");
    expect(state.zoneColor).toBe(GAUGE_COLOR_CRITICAL);
    expect(state.clampedValue).toBe(0);
    expect(state.scaleMax).toBe(25);
    expect(state.needleAngle).toBe(180);
    expect(state.isBelowScale).toBe(true);
    expect(state.actualValue).toBe(-3.2);
  });

  it("treats exactly 0 % as critical/red", () => {
    const state = getGaugeState(0);
    expect(state.zone).toBe("critical");
    expect(state.zoneColor).toBe(GAUGE_COLOR_CRITICAL);
    expect(state.zoneLabel).toBe("kritisch");
    expect(state.needleAngle).toBe(180);
  });

  it("keeps 4.99 % in the critical zone", () => {
    const state = getGaugeState(4.99);
    expect(state.zone).toBe("critical");
    expect(state.zoneColor).toBe(GAUGE_COLOR_CRITICAL);
  });

  it("starts the watch zone at exactly 5 %", () => {
    const state = getGaugeState(5);
    expect(state.zone).toBe("watch");
    expect(state.zoneColor).toBe(GAUGE_COLOR_WATCH);
    expect(state.zoneLabel).toBe("beobachten");
  });

  it("keeps 8.99 % in the watch zone", () => {
    const state = getGaugeState(8.99);
    expect(state.zone).toBe("watch");
    expect(state.zoneColor).toBe(GAUGE_COLOR_WATCH);
  });

  it("starts the positive zone at exactly 9 %", () => {
    const state = getGaugeState(9);
    expect(state.zone).toBe("positive");
    expect(state.zoneColor).toBe(GAUGE_COLOR_POSITIVE);
    expect(state.zoneLabel).toBe("positiv");
  });

  it("places 25 % at the right end of the base scale", () => {
    const state = getGaugeState(25);
    expect(state.zone).toBe("positive");
    expect(state.clampedValue).toBe(25);
    expect(state.scaleMax).toBe(25);
    expect(state.needleAngle).toBe(0);
    expect(state.isAboveScale).toBe(false);
  });

  it("extends the scale above 25 % so the needle shows the real value", () => {
    const state = getGaugeState(31);
    expect(state.actualValue).toBe(31);
    expect(state.scaleMax).toBe(35);
    expect(state.clampedValue).toBe(31);
    expect(state.isAboveScale).toBe(true);
    expect(state.zoneLabel).toBe("über Skala");
    expect(state.scaleMarks).toEqual([0, 5, 9, 25, 35]);
  });

  it("keeps distinct actual values for 37.26 % and 59.19 % with matching needles", () => {
    const ebit = getGaugeState(37.26);
    const roi = getGaugeState(59.19);
    expect(ebit.actualValue).toBe(37.26);
    expect(roi.actualValue).toBe(59.19);
    expect(formatPercentOrDash(ebit.actualValue)).toBe("37,26 %");
    expect(formatPercentOrDash(roi.actualValue)).toBe("59,19 %");
    expect(ebit.scaleMax).toBe(40);
    expect(roi.scaleMax).toBe(60);
    expect(ebit.clampedValue).toBe(37.26);
    expect(roi.clampedValue).toBe(59.19);
    expect(ebit.zoneLabel).toBe("über Skala");
    expect(roi.zoneLabel).toBe("über Skala");
    expect(ebit.needleAngle).toBeGreaterThan(0);
    expect(roi.needleAngle).toBeGreaterThan(0);
    expect(ebit.needleAngle).not.toBe(roi.needleAngle);
  });

  it("returns unavailable for null/NaN/Infinity without invalid angles", () => {
    for (const value of [null, undefined, Number.NaN, Number.POSITIVE_INFINITY]) {
      const state = getGaugeState(value as number | null | undefined);
      expect(state.isAvailable).toBe(false);
      expect(state.zoneLabel).toBe("nicht verfügbar");
      expect(Number.isFinite(state.needleAngle)).toBe(true);
      expect(Number.isFinite(state.clampedValue)).toBe(true);
    }
  });

  it("maps needle angles proportionally without NaN", () => {
    expect(valueToNeedleAngle(0)).toBe(180);
    expect(valueToNeedleAngle(12.5)).toBe(90);
    expect(valueToNeedleAngle(25)).toBe(0);
    expect(valueToNeedleAngle(20, 40)).toBe(90);
    expect(Number.isFinite(valueToNeedleAngle(Number.NaN))).toBe(true);
  });

  it("builds scale marks and nice upper bounds", () => {
    expect(niceGaugeScaleMax(12)).toBe(GAUGE_SCALE_MAX);
    expect(niceGaugeScaleMax(37.26)).toBe(40);
    expect(niceGaugeScaleMax(59.19)).toBe(60);
    expect(buildGaugeScaleMarks(25)).toEqual([0, 5, 9, 25]);
    expect(buildGaugeScaleMarks(40)).toEqual([0, 5, 9, 25, 40]);
    expect(gaugeScaleMarkLeftPercent(0, 40)).toBe(0);
    expect(gaugeScaleMarkLeftPercent(40, 40)).toBe(100);
    expect(gaugeScaleMarkLeftPercent(20, 40)).toBeCloseTo(50);
  });
});
