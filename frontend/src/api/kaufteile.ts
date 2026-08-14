import { api } from "./client";
import type { Kaufteil } from "../types/baugruppe";

export type KaufteilPayload = Omit<Kaufteil, "id" | "created_at" | "updated_at">;

export function listKaufteile(nurAktiv = false) {
  const q = nurAktiv ? "?nur_aktiv=true" : "";
  return api.get<Kaufteil[]>(`/kaufteile${q}`);
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
