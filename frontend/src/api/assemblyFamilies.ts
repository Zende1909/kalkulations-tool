import { api } from "./client";
import type {
  AssemblyFamily,
  AssemblyFamilyMix,
  AssemblyVariant,
  AssemblyVariantWrite,
} from "../types/assemblyFamily";

export function listAssemblyFamilies(params?: { project_id?: number; aktiv?: boolean }) {
  const search = new URLSearchParams();
  if (params?.project_id != null) search.set("project_id", String(params.project_id));
  if (params?.aktiv === true) search.set("aktiv", "true");
  if (params?.aktiv === false) search.set("aktiv", "false");
  const qs = search.toString();
  return api.get<AssemblyFamily[]>(qs ? `/assembly-families?${qs}` : "/assembly-families");
}

export function createAssemblyFamily(body: {
  project_id: number;
  name: string;
  beschreibung?: string;
  status?: string;
  aktiv?: boolean;
}) {
  return api.post<AssemblyFamily>("/assembly-families", body);
}

export function getAssemblyFamily(id: number) {
  return api.get<AssemblyFamily>(`/assembly-families/${id}`);
}

export function updateAssemblyFamily(
  id: number,
  body: Partial<{ name: string; beschreibung: string; status: string; aktiv: boolean }>,
) {
  return api.put<AssemblyFamily>(`/assembly-families/${id}`, body);
}

export function deleteAssemblyFamily(id: number) {
  return api.delete(`/assembly-families/${id}`);
}

export function getAssemblyFamilyMix(id: number) {
  return api.get<AssemblyFamilyMix>(`/assembly-families/${id}/mix`);
}

export function recalculateAssemblyFamily(id: number) {
  return api.post<AssemblyFamilyMix>(`/assembly-families/${id}/recalculate`, {});
}

export function createAssemblyVariant(familyId: number, body: AssemblyVariantWrite) {
  return api.post<AssemblyVariant>(`/assembly-families/${familyId}/variants`, body);
}

export function updateAssemblyVariant(
  familyId: number,
  variantId: number,
  body: Partial<AssemblyVariantWrite>,
) {
  return api.put<AssemblyVariant>(`/assembly-families/${familyId}/variants/${variantId}`, body);
}

export function deleteAssemblyVariant(familyId: number, variantId: number) {
  return api.delete(`/assembly-families/${familyId}/variants/${variantId}`);
}
