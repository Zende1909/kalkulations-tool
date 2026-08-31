/** Payload-Aufbau für die Zykluszeit-Live-Vorschau (IKET). */
import { describe, expect, it } from "vitest";

import {
  emptySpritzgussForm,
  ZYKLUSZEIT_DEFAULT_KUEHLFAKTOR,
  ZYKLUSZEIT_DEFAULT_VARIANTE,
  ZYKLUSZEIT_NEBENZEIT_DEFAULTS,
} from "../types/spritzguss";
import {
  buildZykluszeitPreviewPayload,
  summeNebenzeiten,
} from "./zykluszeitPreview";
import { parseSpritzgussDecimalFields } from "./spritzgussFormDecimals";

describe("buildZykluszeitPreviewPayload", () => {
  it("nutzt IKET-Defaults für Variante, Kühlfaktor und Nebenzeiten", () => {
    const payload = buildZykluszeitPreviewPayload(emptySpritzgussForm(), {});
    expect(payload.zykluszeit_variante).toBe(ZYKLUSZEIT_DEFAULT_VARIANTE);
    expect(payload.zykluszeit_variante).toBe(2);
    expect(payload.zykluszeit_kuehlfaktor).toBe(ZYKLUSZEIT_DEFAULT_KUEHLFAKTOR);
    expect(payload.zykluszeit_kuehlfaktor).toBe(1.5);
    expect(payload.zykluszeit_komponenten).toBe(1);
    expect(summeNebenzeiten(payload)).toBeCloseTo(12.5, 10);
  });

  it("liest Wandstärke live aus decimalRaw", () => {
    const payload = buildZykluszeitPreviewPayload(emptySpritzgussForm(), {
      zykluszeit_wandstaerke_mm: "4,5",
    });
    expect(payload.zykluszeit_wandstaerke_mm).toBeCloseTo(4.5, 10);
  });

  it("liefert ohne Wandstärke null statt 0", () => {
    const payload = buildZykluszeitPreviewPayload(emptySpritzgussForm(), {
      zykluszeit_wandstaerke_mm: "",
    });
    expect(payload.zykluszeit_wandstaerke_mm).toBeNull();
  });

  it("übernimmt geänderte Nebenzeiten aus decimalRaw", () => {
    const payload = buildZykluszeitPreviewPayload(emptySpritzgussForm(), {
      zykluszeit_nz_einlegen_s: "4,5",
      zykluszeit_nz_ausblasen_s: "1",
    });
    expect(payload.zykluszeit_nz_einlegen_s).toBeCloseTo(4.5, 10);
    expect(payload.zykluszeit_nz_ausblasen_s).toBeCloseTo(1, 10);
    expect(summeNebenzeiten(payload)).toBeCloseTo(12.5 - 2 + 4.5 + 1, 10);
  });

  it("fällt bei unvollständiger Eingabe auf den Default zurück", () => {
    const payload = buildZykluszeitPreviewPayload(emptySpritzgussForm(), {
      zykluszeit_kuehlfaktor: "1,",
    });
    expect(payload.zykluszeit_kuehlfaktor).toBe(ZYKLUSZEIT_DEFAULT_KUEHLFAKTOR);
  });

  it("gibt die Materialauswahl weiter", () => {
    const form = { ...emptySpritzgussForm(), material_id: 42 };
    expect(buildZykluszeitPreviewPayload(form, {}).material_id).toBe(42);
  });
});

describe("parseSpritzgussDecimalFields für Zykluszeitfelder", () => {
  it("hält die Wandstärke bei leerem Feld auf null", () => {
    const parsed = parseSpritzgussDecimalFields(
      { zykluszeit_wandstaerke_mm: "" },
      emptySpritzgussForm(),
    );
    expect(parsed.zykluszeit_wandstaerke_mm).toBeNull();
  });

  it("parst Wandstärke und Kühlfaktor in deutscher Schreibweise", () => {
    const parsed = parseSpritzgussDecimalFields(
      { zykluszeit_wandstaerke_mm: "4,5", zykluszeit_kuehlfaktor: "1,8" },
      emptySpritzgussForm(),
    );
    expect(parsed.zykluszeit_wandstaerke_mm).toBeCloseTo(4.5, 10);
    expect(parsed.zykluszeit_kuehlfaktor).toBeCloseTo(1.8, 10);
  });

  it("setzt leere Nebenzeiten auf ihren IKET-Default zurück", () => {
    const parsed = parseSpritzgussDecimalFields(
      { zykluszeit_nz_auswerfen_s: "" },
      emptySpritzgussForm(),
    );
    expect(parsed.zykluszeit_nz_auswerfen_s).toBe(
      ZYKLUSZEIT_NEBENZEIT_DEFAULTS.zykluszeit_nz_auswerfen_s,
    );
    expect(parsed.zykluszeit_nz_auswerfen_s).toBe(2.5);
  });

  it("übernimmt eine explizite 0 als Nebenzeit", () => {
    const parsed = parseSpritzgussDecimalFields(
      { zykluszeit_nz_auswerfen_s: "0" },
      emptySpritzgussForm(),
    );
    expect(parsed.zykluszeit_nz_auswerfen_s).toBe(0);
  });
});
