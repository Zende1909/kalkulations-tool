import { api } from "./client";
import type { BusinessCaseResponse } from "../types/businessCase";

export interface BusinessCaseQuery {
  customer: string;
  project: string;
  calculation_id?: number;
  baugruppe_id?: number;
}

function buildQuery(q: BusinessCaseQuery): string {
  const params = new URLSearchParams();
  params.set("customer", q.customer);
  params.set("project", q.project);
  if (q.calculation_id != null) params.set("calculation_id", String(q.calculation_id));
  if (q.baugruppe_id != null) params.set("baugruppe_id", String(q.baugruppe_id));
  return `?${params.toString()}`;
}

export async function getBusinessCaseOverview(query: BusinessCaseQuery): Promise<BusinessCaseResponse> {
  return api.get<BusinessCaseResponse>(`/business-cases${buildQuery(query)}`);
}

export async function listProjectOptions(): Promise<{ customers: string[]; projects: string[] }> {
  const [kalkulationen, baugruppen] = await Promise.all([
    api.get<Array<{ kunde: string; projekt: string }>>("/spritzguss"),
    api.get<Array<{ kunde: string; projekt: string }>>("/baugruppen"),
  ]);
  const customers = new Set<string>();
  const projects = new Set<string>();
  for (const row of [...kalkulationen, ...baugruppen]) {
    if (row.kunde) customers.add(row.kunde);
    if (row.projekt) projects.add(row.projekt);
  }
  return {
    customers: Array.from(customers).sort(),
    projects: Array.from(projects).sort(),
  };
}
