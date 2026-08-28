import { api } from "./client";
import type { BusinessCaseResponse, ManualPriceUpsert } from "../types/businessCase";

export interface BusinessCaseQuery {
  customer_id: number;
  program_id: number;
  linked_project_id: number;
  calculation_id?: number;
  baugruppe_id?: number;
}

function buildQuery(q: BusinessCaseQuery): string {
  const params = new URLSearchParams();
  params.set("customer_id", String(q.customer_id));
  params.set("program_id", String(q.program_id));
  params.set("linked_project_id", String(q.linked_project_id));
  if (q.calculation_id != null) params.set("calculation_id", String(q.calculation_id));
  if (q.baugruppe_id != null) params.set("baugruppe_id", String(q.baugruppe_id));
  return `?${params.toString()}`;
}

export async function getBusinessCaseOverview(query: BusinessCaseQuery): Promise<BusinessCaseResponse> {
  return api.get<BusinessCaseResponse>(`/business-cases${buildQuery(query)}`);
}

export async function upsertManualPrice(payload: ManualPriceUpsert): Promise<void> {
  await api.put("/business-cases/manual-prices", payload);
}

export function businessCaseXlsxUrl(query: BusinessCaseQuery): string {
  return `/reports/business-case.xlsx${buildQuery(query)}`;
}

export function businessCasePdfUrl(query: BusinessCaseQuery): string {
  return `/reports/business-case.pdf${buildQuery(query)}`;
}
