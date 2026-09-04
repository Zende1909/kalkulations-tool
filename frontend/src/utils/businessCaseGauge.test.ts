import { describe, expect, it } from "vitest";

import {
  GAUGE_COLOR_CRITICAL,
  GAUGE_COLOR_POSITIVE,
  GAUGE_COLOR_WATCH,
  getGaugeState,
  valueToNeedleAngle,
} from "../utils/businessCaseGauge";

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

  it("places 25 % at the right end of the scale", () => {
    const state = getGaugeState(25);
    expect(state.zone).toBe("positive");
    expect(state.clampedValue).toBe(25);
    expect(state.needleAngle).toBe(0);
    expect(state.isAboveScale).toBe(false);
  });

  it("keeps values above 25 % visible but clamps the needle", () => {
    const state = getGaugeState(31);
    expect(state.actualValue).toBe(31);
    expect(state.clampedValue).toBe(25);
    expect(state.needleAngle).toBe(0);
    expect(state.isAboveScale).toBe(true);
    expect(state.zoneLabel).toBe("über Skala");
    expect(state.zoneColor).toBe(GAUGE_COLOR_POSITIVE);
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
    expect(Number.isFinite(valueToNeedleAngle(Number.NaN))).toBe(true);
  });
});
