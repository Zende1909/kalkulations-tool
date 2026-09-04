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
import type { ProjectAssemblyMix } from "../types/projectAssemblyMix";

export type CalcPayload = BaugruppeFormData & {
  spritzguss_zuordnungen: SpritzgussZuordnungInput[];
  kaufteil_zuordnungen: KaufteilZuordnungInput[];
  veredelung_zuordnungen: VeredelungZuordnungInput[];
};

export type SavePayload = CalcPayload & {
  /** Nur bei bestätigtem „Verknüpfung entfernen“ true senden. */
  clear_project_link?: boolean;
  /** Bei Update: leeres Anteilsfeld → Anteil am Projekt entfernen. */
  clear_variant_share?: boolean;
};

export function berechnen(payload: CalcPayload) {
  return api.post<BaugruppeCalcResponse>("/baugruppen/berechnen", payload);
}

export function listBaugruppen(params?: { aktiv?: boolean }) {
  const search = new URLSearchParams();
  if (params?.aktiv === true) search.set("aktiv", "true");
  if (params?.aktiv === false) search.set("aktiv", "false");
  const qs = search.toString();
  return api.get<BaugruppeListItem[]>(qs ? `/baugruppen?${qs}` : "/baugruppen");
}

export function getBaugruppe(id: number) {
  return api.get<Baugruppe>(`/baugruppen/${id}`);
}

export function getProjectAssemblyMix(projectId: number) {
  const search = new URLSearchParams({ project_id: String(projectId) });
  return api.get<ProjectAssemblyMix>(`/baugruppen/project-mix?${search}`);
}

export function createBaugruppe(data: SavePayload) {
  const { clear_project_link: _clear, clear_variant_share: _clearShare, ...createBody } = data;
  return api.post<Baugruppe>("/baugruppen", createBody);
}

export function updateBaugruppe(id: number, data: Partial<SavePayload>) {
  return api.put<Baugruppe>(`/baugruppen/${id}`, data);
}

/** Weiches Archivieren (aktiv=false, status=archiviert). */
export function archivierenBaugruppe(id: number) {
  return api.post<void>(`/baugruppen/${id}/archivieren`, {});
}

/** Endgültiges Löschen inkl. eigener Positionsdaten. */
export function deleteBaugruppe(id: number) {
  return api.delete(`/baugruppen/${id}`);
}
