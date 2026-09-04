import { describe, expect, it } from "vitest";

import {
  GAUGE_COLOR_CRITICAL,
  GAUGE_COLOR_POSITIVE,
  GAUGE_COLOR_WATCH,
  GAUGE_SCALE_MARKS,
  GAUGE_SCALE_MAX,
  gaugeArcLabelPosition,
  getGaugeState,
  needleZoneColor,
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
    expect(state.needleAngle).toBe(180);
    expect(state.isBelowScale).toBe(true);
    expect(state.actualValue).toBe(-3.2);
  });

  it("treats exactly 0 % as critical/red", () => {
    const state = getGaugeState(0);
    expect(state.zone).toBe("critical");
    expect(state.zoneColor).toBe(GAUGE_COLOR_CRITICAL);
    expect(state.zoneLabel).toBe("kritisch");
  });

  it("starts the watch zone at exactly 5 %", () => {
    const state = getGaugeState(5);
    expect(state.zone).toBe("watch");
    expect(state.zoneColor).toBe(GAUGE_COLOR_WATCH);
    expect(state.zoneLabel).toBe("beobachten");
  });

  it("starts the positive zone at exactly 9 %", () => {
    const state = getGaugeState(9);
    expect(state.zone).toBe("positive");
    expect(state.zoneColor).toBe(GAUGE_COLOR_POSITIVE);
    expect(state.zoneLabel).toBe("positiv");
  });

  it("places 25 % at the right end of the scale", () => {
    const state = getGaugeState(25);
    expect(state.clampedValue).toBe(25);
    expect(state.needleAngle).toBe(0);
    expect(state.zoneColor).toBe(GAUGE_COLOR_POSITIVE);
    expect(state.isAboveScale).toBe(false);
  });

  it("clamps needle at outer edge above 25 % but keeps value color green", () => {
    const state = getGaugeState(59.19);
    expect(state.actualValue).toBe(59.19);
    expect(formatPercentOrDash(state.actualValue)).toBe("59,19 %");
    expect(state.clampedValue).toBe(GAUGE_SCALE_MAX);
    expect(state.needleAngle).toBe(0);
    expect(state.isAboveScale).toBe(true);
    expect(state.zoneLabel).toBe("über Skala");
    expect(state.zoneColor).toBe(GAUGE_COLOR_POSITIVE);
  });

  it("keeps distinct actual values for 37.26 % and 59.19 %", () => {
    const ebit = getGaugeState(37.26);
    const roi = getGaugeState(59.19);
    expect(formatPercentOrDash(ebit.actualValue)).toBe("37,26 %");
    expect(formatPercentOrDash(roi.actualValue)).toBe("59,19 %");
    expect(ebit.clampedValue).toBe(25);
    expect(roi.clampedValue).toBe(25);
  });

  it("returns unavailable for null/NaN/Infinity without invalid angles", () => {
    for (const value of [null, undefined, Number.NaN, Number.POSITIVE_INFINITY]) {
      const state = getGaugeState(value as number | null | undefined);
      expect(state.isAvailable).toBe(false);
      expect(Number.isFinite(state.needleAngle)).toBe(true);
    }
  });

  it("maps needle angles and arc label positions without NaN", () => {
    expect(valueToNeedleAngle(0)).toBe(180);
    expect(valueToNeedleAngle(12.5)).toBe(90);
    expect(valueToNeedleAngle(25)).toBe(0);

    const left = gaugeArcLabelPosition(0);
    const mid = gaugeArcLabelPosition(12.5);
    const right = gaugeArcLabelPosition(25);
    expect(left.leftPercent).toBeLessThan(mid.leftPercent);
    expect(mid.leftPercent).toBeLessThan(right.leftPercent);
    expect(mid.topPercent).toBeLessThan(left.topPercent);
    expect(mid.topPercent).toBeLessThan(right.topPercent);
    for (const mark of GAUGE_SCALE_MARKS) {
      const pos = gaugeArcLabelPosition(mark);
      expect(Number.isFinite(pos.leftPercent)).toBe(true);
      expect(Number.isFinite(pos.topPercent)).toBe(true);
    }
  });

  it("maps needle zone colors for value display", () => {
    expect(needleZoneColor(0, false)).toBe(GAUGE_COLOR_CRITICAL);
    expect(needleZoneColor(5, false)).toBe(GAUGE_COLOR_WATCH);
    expect(needleZoneColor(9, false)).toBe(GAUGE_COLOR_POSITIVE);
    expect(needleZoneColor(25, false)).toBe(GAUGE_COLOR_POSITIVE);
    expect(needleZoneColor(0, true)).toBe(GAUGE_COLOR_CRITICAL);
  });
});
