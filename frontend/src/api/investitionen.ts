import { api } from "./client";
import type {
  BusinessCaseFilters,
  Investition,
  InvestitionPayload,
  InvestitionTarget,
  InvestitionTargetFilters,
} from "../types/investition";

function buildQuery(filters: BusinessCaseFilters = {}): string {
  const params = new URLSearchParams();
  if (filters.project) params.set("project", filters.project);
  if (filters.linked_project_id != null) {
    params.set("linked_project_id", String(filters.linked_project_id));
  }
  if (filters.customer) params.set("customer", filters.customer);
  if (filters.customer_id != null) params.set("customer_id", String(filters.customer_id));
  if (filters.program_id != null) params.set("program_id", String(filters.program_id));
  if (filters.calculation_id != null) params.set("calculation_id", String(filters.calculation_id));
  if (filters.baugruppe_id != null) params.set("baugruppe_id", String(filters.baugruppe_id));
  if (filters.kaufteil_id != null) params.set("kaufteil_id", String(filters.kaufteil_id));
  if (filters.assignment_type) params.set("assignment_type", filters.assignment_type);
  if (filters.scope) params.set("scope", filters.scope);
  const q = params.toString();
  return q ? `?${q}` : "";
}

function buildTargetQuery(filters: InvestitionTargetFilters): string {
  const params = new URLSearchParams({
    customer_id: String(filters.customer_id),
    program_id: String(filters.program_id),
    project_id: String(filters.project_id),
    assignment_type: filters.assignment_type,
  });
  return `?${params.toString()}`;
}

export async function listInvestitionTargets(
  filters: InvestitionTargetFilters,
): Promise<InvestitionTarget[]> {
  return api.get<InvestitionTarget[]>(`/investitionen/targets${buildTargetQuery(filters)}`);
}

export async function listInvestitionen(filters?: BusinessCaseFilters): Promise<Investition[]> {
  if (!filters?.project && filters?.linked_project_id == null) {
    return [];
  }
  return api.get<Investition[]>(`/investitionen${buildQuery(filters)}`);
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
