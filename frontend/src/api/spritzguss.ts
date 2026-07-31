import { api } from "./client";
import type {
  SpritzgussCalcResponse,
  SpritzgussFormData,
  SpritzgussKalkulation,
  SpritzgussListItem,
} from "../types/spritzguss";

export type CalcPayload = Pick<
  SpritzgussFormData,
  | "teilegewicht_netto_g"
  | "materialpreis_pro_kg"
  | "ausschussquote_pct"
  | "mgk_pct"
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
>;

export function berechnen(payload: CalcPayload) {
  return api.post<SpritzgussCalcResponse>("/spritzguss/berechnen", payload);
}

export function listKalkulationen() {
  return api.get<SpritzgussListItem[]>("/spritzguss");
}

export function getKalkulation(id: number) {
  return api.get<SpritzgussKalkulation>(`/spritzguss/${id}`);
}

export function createKalkulation(data: SpritzgussFormData) {
  return api.post<SpritzgussKalkulation>("/spritzguss", data);
}

export function updateKalkulation(id: number, data: Partial<SpritzgussFormData>) {
  return api.put<SpritzgussKalkulation>(`/spritzguss/${id}`, data);
}

export function deleteKalkulation(id: number) {
  return api.delete(`/spritzguss/${id}`);
}
