import { api } from "./client";
import type {
  Baugruppe,
  BaugruppeCalcResponse,
  BaugruppeFormData,
  BaugruppeListItem,
  KaufteilZuordnungInput,
  SpritzgussZuordnungInput,
  VeredelungZuordnungInput,
} from "../types/baugruppe";

export type CalcPayload = BaugruppeFormData & {
  spritzguss_zuordnungen: SpritzgussZuordnungInput[];
  kaufteil_zuordnungen: KaufteilZuordnungInput[];
  veredelung_zuordnungen: VeredelungZuordnungInput[];
};

export type SavePayload = CalcPayload & {
  /** Nur bei bestätigtem „Verknüpfung entfernen“ true senden. */
  clear_project_link?: boolean;
};

export function berechnen(payload: CalcPayload) {
  return api.post<BaugruppeCalcResponse>("/baugruppen/berechnen", payload);
}

export function listBaugruppen() {
  return api.get<BaugruppeListItem[]>("/baugruppen");
}

export function getBaugruppe(id: number) {
  return api.get<Baugruppe>(`/baugruppen/${id}`);
}

export function createBaugruppe(data: SavePayload) {
  const { clear_project_link: _clear, ...createBody } = data;
  return api.post<Baugruppe>("/baugruppen", createBody);
}

export function updateBaugruppe(id: number, data: Partial<SavePayload>) {
  return api.put<Baugruppe>(`/baugruppen/${id}`, data);
}

export function deleteBaugruppe(id: number) {
  return api.delete(`/baugruppen/${id}`);
}
