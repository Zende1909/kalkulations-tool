import { describe, expect, it } from "vitest";

import {
  formatCost,
  formatEbitWithPercent,
  formatMarginPercent,
  formatMarginWithPercent,
  formatManualPrice,
  formatPercentOrDash,
  formatRevenueEuro,
} from "./businessCaseFormatting";

describe("businessCaseFormatting revenue", () => {
  it("formats revenue as whole euros", () => {
    expect(formatRevenueEuro(28000.49)).toBe("28.000 €");
    expect(formatRevenueEuro(28000.51)).toBe("28.001 €");
  });
});

describe("businessCaseFormatting", () => {
  it("shows nicht hinterlegt for missing costs", () => {
    expect(formatCost(null)).toBe("nicht hinterlegt");
    expect(formatCost(undefined)).toBe("nicht hinterlegt");
    expect(formatCost(null, false)).toBe("nicht hinterlegt");
  });

  it("shows costs when present", () => {
    expect(formatCost(10.5)).toBe("10,50 €");
    expect(formatCost(10.5, true)).toBe("10,50 €");
  });

  it("formats margin percent with two decimals de-DE", () => {
    expect(formatMarginPercent(9.555)).toBe("9,56 %");
    expect(formatMarginPercent(-3.2)).toBe("-3,20 %");
  });

  it("returns dash for division by zero base", () => {
    expect(formatMarginPercent(null)).toBe("–");
  });

  it("combines margin euro and percent", () => {
    expect(formatMarginWithPercent(1000, 9.56)).toBe("1.000,00 € (9,56 %)");
  });

  it("formats EBIT helper", () => {
    expect(formatEbitWithPercent(-20000, -25)).toBe("-20.000,00 € (-25,00 %)");
  });

  it("formats percent or dash", () => {
    expect(formatPercentOrDash(9.555)).toBe("9,56 %");
    expect(formatPercentOrDash(null)).toBe("–");
  });

  it("manual price shows nicht hinterlegt without flag", () => {
    expect(formatManualPrice(14, false)).toBe("nicht hinterlegt");
    expect(formatManualPrice(14, true)).toBe("14,00 €");
  });
});
