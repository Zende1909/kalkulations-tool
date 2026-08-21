import { api } from "./client";
import type { Kaufteil } from "../types/baugruppe";

export type KaufteilPayload = Omit<Kaufteil, "id" | "created_at" | "updated_at">;

export function listKaufteile(
  options: {
    nurAktiv?: boolean;
    customerId?: number;
    programId?: number;
    projectId?: number;
  } = {},
) {
  const params = new URLSearchParams();
  if (options.nurAktiv) params.set("nur_aktiv", "true");
  if (options.customerId != null) params.set("customer_id", String(options.customerId));
  if (options.programId != null) params.set("program_id", String(options.programId));
  if (options.projectId != null) params.set("project_id", String(options.projectId));
  const q = params.toString();
  return api.get<Kaufteil[]>(`/kaufteile${q ? `?${q}` : ""}`);
}


export function getKaufteil(id: number) {
  return api.get<Kaufteil>(`/kaufteile/${id}`);
}

export function createKaufteil(data: KaufteilPayload) {
  return api.post<Kaufteil>("/kaufteile", data);
}

export function updateKaufteil(id: number, data: Partial<KaufteilPayload>) {
  return api.put<Kaufteil>(`/kaufteile/${id}`, data);
}

export function deleteKaufteil(id: number) {
  return api.delete(`/kaufteile/${id}`);
}
