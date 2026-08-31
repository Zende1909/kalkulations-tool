/**
 * Payload für die Live-Vorschau der Zykluszeit-Schätzung.
 *
 * Gelesen wird bevorzugt aus `decimalRaw`, damit der Vorschlag schon während
 * der Eingabe aktuell ist; das geparste Formular dient als Rückfallebene.
 */

import type { SpritzgussFormData } from "../types/spritzguss";
import { ZYKLUSZEIT_DEFAULT_GROESSENKLASSE } from "../types/spritzguss";
import { coerceFormDecimal } from "./decimalInput";

export interface ZykluszeitPreviewPayload {
  material_id: number | null;
  zykluszeit_wandstaerke_mm: number | null;
  zykluszeit_groessenklasse: string;
  zykluszeit_nebenzeiten_gesamt_s: number | null;
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
  return {
    material_id: form.material_id,
    zykluszeit_wandstaerke_mm: readZykluszeitDecimal(
      decimalRaw,
      form,
      "zykluszeit_wandstaerke_mm",
      null,
    ),
    zykluszeit_groessenklasse:
      form.zykluszeit_groessenklasse || ZYKLUSZEIT_DEFAULT_GROESSENKLASSE,
    zykluszeit_nebenzeiten_gesamt_s: readZykluszeitDecimal(
      decimalRaw,
      form,
      "zykluszeit_nebenzeiten_gesamt_s",
      null,
    ),
  };
}
