import { api } from "./client";
import type {
  BusinessCaseFilters,
  BusinessCaseSummary,
  Investition,
  InvestitionPayload,
} from "../types/investition";

function buildQuery(filters: BusinessCaseFilters = {}): string {
  const params = new URLSearchParams();
  if (filters.project) params.set("project", filters.project);
  if (filters.customer) params.set("customer", filters.customer);
  if (filters.calculation_id != null) params.set("calculation_id", String(filters.calculation_id));
  if (filters.baugruppe_id != null) params.set("baugruppe_id", String(filters.baugruppe_id));
  if (filters.scope) params.set("scope", filters.scope);
  const q = params.toString();
  return q ? `?${q}` : "";
}

export async function listInvestitionen(filters?: BusinessCaseFilters): Promise<Investition[]> {
  return api.get<Investition[]>(`/investitionen${buildQuery(filters)}`);
}

export async function getBusinessCase(filters?: BusinessCaseFilters): Promise<BusinessCaseSummary> {
  return api.get<BusinessCaseSummary>(`/investitionen/business-case${buildQuery(filters)}`);
}

export async function getInvestition(id: number): Promise<Investition> {
  return api.get<Investition>(`/investitionen/${id}`);
}

export async function createInvestition(body: InvestitionPayload): Promise<Investition> {
  return api.post<Investition>("/investitionen", body);
}

export async function updateInvestition(id: number, body: Partial<InvestitionPayload>): Promise<Investition> {
  return api.put<Investition>(`/investitionen/${id}`, body);
}

export async function archiveInvestition(id: number): Promise<void> {
  return api.delete(`/investitionen/${id}`);
}
