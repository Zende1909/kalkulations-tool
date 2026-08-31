import type { MaschinenGroesseModus, SpritzgussFormData } from "../types/spritzguss";
import { coerceFormDecimal, parsePercentPointsInput } from "./decimalInput";

export interface MaschinenGroessePreviewPayload {
  maschinen_groesse_modus: MaschinenGroesseModus;
  maschinen_groesse_breite_mm?: number | null;
  maschinen_groesse_laenge_mm?: number | null;
  maschinen_groesse_oeffnungen_pct?: number | null;
  maschinen_groesse_proj_flaeche_mm2?: number | null;
  maschinen_groesse_schwindung_pct: number;
  material_id: number | null;
  kavitaeten: number;
  werk_id: number | null;
}

function readDecimalField(
  decimalRaw: Record<string, string>,
  form: SpritzgussFormData,
  key: keyof SpritzgussFormData,
): number | null {
  const text = (decimalRaw[key as string] ?? "").trim();
  if (text === "") {
    const fallback = form[key];
    return typeof fallback === "number" ? fallback : null;
  }
  try {
    return coerceFormDecimal(text, "Dezimalzahl");
  } catch {
    return null;
  }
}

function readPercentField(
  decimalRaw: Record<string, string>,
  form: SpritzgussFormData,
  key: keyof SpritzgussFormData,
): number | null {
  const text = (decimalRaw[key as string] ?? "").trim();
  if (text === "") {
    const fallback = form[key];
    return typeof fallback === "number" ? fallback : null;
  }
  try {
    return parsePercentPointsInput(text);
  } catch {
    return null;
  }
}

export function readKavitaeten(
  decimalRaw: Record<string, string>,
  fallback = 1,
): number {
  const text = (decimalRaw.kavitaeten ?? "").trim();
  if (text === "") return fallback;
  const parsed = Number(text.replace(",", "."));
  if (!Number.isFinite(parsed) || !Number.isInteger(parsed) || parsed < 1) {
    return fallback;
  }
  return parsed;
}

export function buildMaschinenGroessePreviewPayload(
  form: SpritzgussFormData,
  decimalRaw: Record<string, string>,
): MaschinenGroessePreviewPayload | null {
  if (form.maschinen_groesse_modus == null) return null;

  const schwindung = readPercentField(
    decimalRaw,
    form,
    "maschinen_groesse_schwindung_pct",
  );
  if (schwindung == null) return null;

  const kavitaeten = readKavitaeten(decimalRaw, form.kavitaeten);
  const payload: MaschinenGroessePreviewPayload = {
    maschinen_groesse_modus: form.maschinen_groesse_modus,
    maschinen_groesse_schwindung_pct: schwindung,
    material_id: form.material_id,
    kavitaeten,
    werk_id: form.werk_id,
  };

  if (form.maschinen_groesse_modus === "masse") {
    payload.maschinen_groesse_breite_mm = readDecimalField(
      decimalRaw,
      form,
      "maschinen_groesse_breite_mm",
    );
    payload.maschinen_groesse_laenge_mm = readDecimalField(
      decimalRaw,
      form,
      "maschinen_groesse_laenge_mm",
    );
    payload.maschinen_groesse_oeffnungen_pct = readPercentField(
      decimalRaw,
      form,
      "maschinen_groesse_oeffnungen_pct",
    );
    if (
      payload.maschinen_groesse_breite_mm == null ||
      payload.maschinen_groesse_laenge_mm == null ||
      payload.maschinen_groesse_oeffnungen_pct == null
    ) {
      return null;
    }
  } else {
    payload.maschinen_groesse_proj_flaeche_mm2 = readDecimalField(
      decimalRaw,
      form,
      "maschinen_groesse_proj_flaeche_mm2",
    );
    if (payload.maschinen_groesse_proj_flaeche_mm2 == null) return null;
  }

  return payload;
}
