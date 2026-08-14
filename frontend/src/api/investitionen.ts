import { api } from "./client";
import type {
  Investition,
  InvestitionFilters,
  InvestitionPayload,
  InvestitionSummary,
} from "../types/investition";

function buildQuery(filters: InvestitionFilters = {}): string {
  const params = new URLSearchParams();
  if (filters.project) params.set("project", filters.project);
  if (filters.customer) params.set("customer", filters.customer);
  if (filters.investment_type) params.set("investment_type", filters.investment_type);
  if (filters.payment_type) params.set("payment_type", filters.payment_type);
  if (filters.status) params.set("status", filters.status);
  if (filters.search) params.set("search", filters.search);
  if (filters.sort_by) params.set("sort_by", filters.sort_by);
  if (filters.sort_dir) params.set("sort_dir", filters.sort_dir);
  const q = params.toString();
  return q ? `?${q}` : "";
}

export async function listInvestitionen(filters?: InvestitionFilters): Promise<Investition[]> {
  return api.get<Investition[]>(`/investitionen${buildQuery(filters)}`);
}

export async function getInvestitionSummary(filters?: InvestitionFilters): Promise<InvestitionSummary> {
  return api.get<InvestitionSummary>(`/investitionen/summary${buildQuery(filters)}`);
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
