/**
 * Payload für die Live-Vorschau des Zykluszeitvorschlags (IKET).
 *
 * Gelesen wird bevorzugt aus `decimalRaw`, damit der Vorschlag schon während
 * der Eingabe aktuell ist; das geparste Formular dient als Rückfallebene.
 */

import type { SpritzgussFormData } from "../types/spritzguss";
import {
  ZYKLUSZEIT_DEFAULT_KUEHLFAKTOR,
  ZYKLUSZEIT_DEFAULT_VARIANTE,
  ZYKLUSZEIT_NEBENZEITEN,
  ZYKLUSZEIT_NEBENZEIT_DEFAULTS,
} from "../types/spritzguss";
import { coerceFormDecimal } from "./decimalInput";

export interface ZykluszeitPreviewPayload {
  material_id: number | null;
  zykluszeit_wandstaerke_mm: number | null;
  zykluszeit_variante: number;
  zykluszeit_kuehlfaktor: number;
  zykluszeit_komponenten: number;
  [nebenzeit: string]: number | null;
}

export function readZykluszeitDecimal(
  decimalRaw: Record<string, string>,
  form: SpritzgussFormData,
  key: string,
  fallback: number | null,
): number | null {
  const text = (decimalRaw[key] ?? "").trim();
  if (text === "") {
    const ausForm = (form as unknown as Record<string, unknown>)[key];
    return typeof ausForm === "number" ? ausForm : fallback;
  }
  try {
    const parsed = coerceFormDecimal(text, "Dezimalzahl");
    return parsed == null || !Number.isFinite(parsed) ? fallback : parsed;
  } catch {
    return fallback;
  }
}

export function buildZykluszeitPreviewPayload(
  form: SpritzgussFormData,
  decimalRaw: Record<string, string>,
): ZykluszeitPreviewPayload {
  const payload: ZykluszeitPreviewPayload = {
    material_id: form.material_id,
    zykluszeit_wandstaerke_mm: readZykluszeitDecimal(
      decimalRaw,
      form,
      "zykluszeit_wandstaerke_mm",
      null,
    ),
    zykluszeit_variante: form.zykluszeit_variante || ZYKLUSZEIT_DEFAULT_VARIANTE,
    zykluszeit_kuehlfaktor:
      readZykluszeitDecimal(
        decimalRaw,
        form,
        "zykluszeit_kuehlfaktor",
        ZYKLUSZEIT_DEFAULT_KUEHLFAKTOR,
      ) ?? ZYKLUSZEIT_DEFAULT_KUEHLFAKTOR,
    zykluszeit_komponenten: form.zykluszeit_komponenten || 1,
  };

  for (const { feld } of ZYKLUSZEIT_NEBENZEITEN) {
    payload[feld] =
      readZykluszeitDecimal(decimalRaw, form, feld, ZYKLUSZEIT_NEBENZEIT_DEFAULTS[feld]) ??
      ZYKLUSZEIT_NEBENZEIT_DEFAULTS[feld];
  }

  return payload;
}

export function summeNebenzeiten(payload: ZykluszeitPreviewPayload): number {
  return ZYKLUSZEIT_NEBENZEITEN.reduce(
    (summe, { feld }) => summe + (payload[feld] ?? 0),
    0,
  );
}
