import { api } from "./client";
import type { AssemblyOverview, DashboardQuery, DashboardSummary } from "../types/dashboard";

function toSearch(params?: DashboardQuery): string {
  const search = new URLSearchParams();
  if (params?.project) search.set("project", params.project);
  if (params?.customer) search.set("customer", params.customer);
  if (params?.status) search.set("status", params.status);
  if (params?.date_from) search.set("date_from", params.date_from);
  if (params?.date_to) search.set("date_to", params.date_to);
  if (params?.kalkulationsart) search.set("kalkulationsart", params.kalkulationsart);
  const query = search.toString();
  return query ? `?${query}` : "";
}

export function getDashboardSummary(params?: DashboardQuery) {
  return api.get<DashboardSummary>(`/dashboard/summary${toSearch(params)}`);
}

export function getAssemblyOverview(assemblyId: number) {
  return api.get<AssemblyOverview>(`/dashboard/assemblies/${assemblyId}`);
}
