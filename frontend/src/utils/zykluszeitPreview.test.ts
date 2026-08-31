/** Payload-Aufbau für die Live-Vorschau der Zykluszeit-Schätzung. */
import { describe, expect, it } from "vitest";

import {
  emptySpritzgussForm,
  nebenzeitenRichtwert,
  ZYKLUSZEIT_DEFAULT_GROESSENKLASSE,
  ZYKLUSZEIT_GROESSENKLASSEN,
} from "../types/spritzguss";
import { buildZykluszeitPreviewPayload } from "./zykluszeitPreview";
import { parseSpritzgussDecimalFields } from "./spritzgussFormDecimals";

describe("Größenklassen", () => {
  it("hat drei Klassen mit Nebenzeiten-Richtwerten", () => {
    expect(ZYKLUSZEIT_GROESSENKLASSEN.map((k) => k.key)).toEqual([
      "klein",
      "mittel",
      "gross",
    ]);
    expect(ZYKLUSZEIT_GROESSENKLASSEN.map((k) => k.nebenzeiten)).toEqual([6, 10, 16]);
  });

  it("liefert für unbekannte Klassen den Default-Richtwert", () => {
    expect(nebenzeitenRichtwert("klein")).toBe(6);
    expect(nebenzeitenRichtwert("gross")).toBe(16);
    expect(nebenzeitenRichtwert(null)).toBe(10);
    expect(nebenzeitenRichtwert("gibtsnicht")).toBe(10);
  });
});

describe("buildZykluszeitPreviewPayload", () => {
  it("nutzt die Default-Größenklasse und keine eigenen Nebenzeiten", () => {
    const payload = buildZykluszeitPreviewPayload(emptySpritzgussForm(), {});
    expect(payload.zykluszeit_groessenklasse).toBe(ZYKLUSZEIT_DEFAULT_GROESSENKLASSE);
    expect(payload.zykluszeit_groessenklasse).toBe("mittel");
    expect(payload.zykluszeit_nebenzeiten_gesamt_s).toBeNull();
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

  it("übernimmt die gewählte Größenklasse", () => {
    const form = { ...emptySpritzgussForm(), zykluszeit_groessenklasse: "gross" as const };
    expect(buildZykluszeitPreviewPayload(form, {}).zykluszeit_groessenklasse).toBe("gross");
  });

  it("übergibt eigene Nebenzeiten live aus decimalRaw", () => {
    const payload = buildZykluszeitPreviewPayload(emptySpritzgussForm(), {
      zykluszeit_nebenzeiten_gesamt_s: "13,5",
    });
    expect(payload.zykluszeit_nebenzeiten_gesamt_s).toBeCloseTo(13.5, 10);
  });

  it("fällt bei unvollständiger Eingabe auf null zurück", () => {
    const payload = buildZykluszeitPreviewPayload(emptySpritzgussForm(), {
      zykluszeit_wandstaerke_mm: "4,",
    });
    expect(payload.zykluszeit_wandstaerke_mm).toBeNull();
  });

  it("gibt die Materialauswahl weiter", () => {
    const form = { ...emptySpritzgussForm(), material_id: 42 };
    expect(buildZykluszeitPreviewPayload(form, {}).material_id).toBe(42);
  });
});

describe("parseSpritzgussDecimalFields für Zykluszeitfelder", () => {
  it("hält Wandstärke und Nebenzeiten bei leerem Feld auf null", () => {
    const parsed = parseSpritzgussDecimalFields(
      { zykluszeit_wandstaerke_mm: "", zykluszeit_nebenzeiten_gesamt_s: "" },
      emptySpritzgussForm(),
    );
    expect(parsed.zykluszeit_wandstaerke_mm).toBeNull();
    expect(parsed.zykluszeit_nebenzeiten_gesamt_s).toBeNull();
  });

  it("parst deutsche Schreibweise", () => {
    const parsed = parseSpritzgussDecimalFields(
      { zykluszeit_wandstaerke_mm: "4,5", zykluszeit_nebenzeiten_gesamt_s: "13,5" },
      emptySpritzgussForm(),
    );
    expect(parsed.zykluszeit_wandstaerke_mm).toBeCloseTo(4.5, 10);
    expect(parsed.zykluszeit_nebenzeiten_gesamt_s).toBeCloseTo(13.5, 10);
  });

  it("übernimmt eine explizite 0 als Nebenzeit", () => {
    const parsed = parseSpritzgussDecimalFields(
      { zykluszeit_nebenzeiten_gesamt_s: "0" },
      emptySpritzgussForm(),
    );
    expect(parsed.zykluszeit_nebenzeiten_gesamt_s).toBe(0);
  });
});
