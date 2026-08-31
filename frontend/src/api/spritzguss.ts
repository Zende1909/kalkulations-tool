import { api } from "./client";
import type {
  MaschinenGroesseResult,
  SpritzgussCalcResponse,
  SpritzgussFormData,
  SpritzgussKalkulation,
  SpritzgussListItem,
  VeredelungZuordnungInput,
  ZykluszeitVorschlag,
} from "../types/spritzguss";
import type { MaschinenGroessePreviewPayload } from "../utils/maschinenGroessePreview";
import type { ZykluszeitPreviewPayload } from "../utils/zykluszeitPreview";

export type { MaschinenGroessePreviewPayload, ZykluszeitPreviewPayload };

export type CalcPayload = Pick<
  SpritzgussFormData,
  | "teilegewicht_netto_g"
  | "schussgewicht_g"
  | "materialpreis_pro_kg"
  | "material_id"
  | "ausschussquote_pct"
  | "mgk_pct"
  | "material_nominierung"
  | "zykluszeit_s"
  | "maschinenstundensatz"
  | "kavitaeten"
  | "lohnstundensatz"
  | "fgk_pct"
  | "werkzeugkosten_eur"
  | "werkzeug_abrechnungsart"
  | "amortisationsvolumen"
  | "vvgk_pct"
  | "gewinn_pct"
  | "skonto_pct"
  | "werk_id"
  | "project_id"
  | "losgroesse_modus"
  | "losgroesse_manuell"
  | "setup_zeit_min"
  | "setup_maschinenstundensatz"
  | "setup_lohnstundensatz"
  | "setup_mitarbeiter"
  | "setup_aktiv"
  | "maschinen_groesse_modus"
  | "maschinen_groesse_breite_mm"
  | "maschinen_groesse_laenge_mm"
  | "maschinen_groesse_oeffnungen_pct"
  | "maschinen_groesse_proj_flaeche_mm2"
  | "zykluszeit_quelle"
  | "zykluszeit_wandstaerke_mm"
  | "zykluszeit_variante"
  | "zykluszeit_kuehlfaktor"
  | "zykluszeit_komponenten"
  | "zykluszeit_nz_werkzeug_schliessen_s"
  | "zykluszeit_nz_duese_anlegen_s"
  | "zykluszeit_nz_einspritzen_s"
  | "zykluszeit_nz_werkzeug_oeffnen_s"
  | "zykluszeit_nz_auswerfen_s"
  | "zykluszeit_nz_kernzug_s"
  | "zykluszeit_nz_ausschrauben_s"
  | "zykluszeit_nz_einlegen_s"
  | "zykluszeit_nz_ausblasen_s"
> & {
  veredelung_zuordnungen?: VeredelungZuordnungInput[];
};

export type SavePayload = SpritzgussFormData & {
  veredelung_zuordnungen?: VeredelungZuordnungInput[];
};

export function berechnen(payload: CalcPayload) {
  return api.post<SpritzgussCalcResponse>("/spritzguss/berechnen", payload);
}

export function berechneMaschinenGroesse(payload: MaschinenGroessePreviewPayload) {
  return api.post<MaschinenGroesseResult>("/spritzguss/maschinen-groesse/berechnen", payload);
}

export function berechneZykluszeit(payload: ZykluszeitPreviewPayload) {
  return api.post<ZykluszeitVorschlag>("/spritzguss/zykluszeit/berechnen", payload);
}

export function listKalkulationen(
  options: { nurAktiv?: boolean; projectId?: number } = {},
) {
  const params = new URLSearchParams();
  if (options.nurAktiv) params.set("nur_aktiv", "true");
  if (options.projectId != null) params.set("project_id", String(options.projectId));
  const q = params.toString();
  return api.get<SpritzgussListItem[]>(`/spritzguss${q ? `?${q}` : ""}`);
}

export function getKalkulation(id: number) {
  return api.get<SpritzgussKalkulation>(`/spritzguss/${id}`);
}

export function createKalkulation(data: SavePayload) {
  return api.post<SpritzgussKalkulation>("/spritzguss", data);
}

export function updateKalkulation(id: number, data: Partial<SavePayload>) {
  return api.put<SpritzgussKalkulation>(`/spritzguss/${id}`, data);
}

export function deleteKalkulation(id: number) {
  return api.delete(`/spritzguss/${id}`);
}
