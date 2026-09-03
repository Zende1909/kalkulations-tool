/**
 * Payload für die Live-Vorschau der Zykluszeit-Schätzung.
 *
 * Gelesen wird bevorzugt aus `decimalRaw`, damit der Vorschlag schon während
 * der Eingabe aktuell ist; das geparste Formular dient als Rückfallebene.
 */

import type { SpritzgussFormData } from "../types/spritzguss";
import {
  ZYKLUSZEIT_DEFAULT_ENTNAHMEART,
  ZYKLUSZEIT_DEFAULT_GROESSENKLASSE,
  ZYKLUSZEIT_DEFAULT_PROZESSAUFWAND,
} from "../types/spritzguss";
import { coerceFormDecimal } from "./decimalInput";

export interface ZykluszeitPreviewPayload {
  material_id: number | null;
  zykluszeit_wandstaerke_mm: number | null;
  zykluszeit_groessenklasse: string;
  zykluszeit_prozessaufwand: string;
  zykluszeit_entnahmeart: string;
  zykluszeit_nebenzeiten_gesamt_s: number | null;
  /** Aus der Maschinengrößen-Vorschau; enthält Kavitäten und Fläche. */
  zuhaltekraft_t: number | null;
  /** Ersatzweise Zuhaltekraft der gewählten Maschine. */
  maschinen_zuhaltekraft_t: number | null;
  /** Für Einspritzzeit, Dosierüberhang und Greiferzuschlag. */
  schussgewicht_g: number | null;
  kavitaeten: number | null;
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
  zuhaltekraftT: number | null = null,
  maschinenZuhaltekraftT: number | null = null,
): ZykluszeitPreviewPayload {
  const schussgewicht = readZykluszeitDecimal(decimalRaw, form, "schussgewicht_g", null);
  const kavitaeten = readZykluszeitDecimal(decimalRaw, form, "kavitaeten", null);
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
    zykluszeit_prozessaufwand:
      form.zykluszeit_prozessaufwand || ZYKLUSZEIT_DEFAULT_PROZESSAUFWAND,
    zykluszeit_entnahmeart: form.zykluszeit_entnahmeart || ZYKLUSZEIT_DEFAULT_ENTNAHMEART,
    zykluszeit_nebenzeiten_gesamt_s: readZykluszeitDecimal(
      decimalRaw,
      form,
      "zykluszeit_nebenzeiten_gesamt_s",
      null,
    ),
    zuhaltekraft_t:
      zuhaltekraftT != null && Number.isFinite(zuhaltekraftT) ? zuhaltekraftT : null,
    maschinen_zuhaltekraft_t:
      maschinenZuhaltekraftT != null && Number.isFinite(maschinenZuhaltekraftT)
        ? maschinenZuhaltekraftT
        : null,
    schussgewicht_g: schussgewicht != null && schussgewicht > 0 ? schussgewicht : null,
    kavitaeten: kavitaeten != null && kavitaeten >= 1 ? Math.floor(kavitaeten) : null,
  };
}
