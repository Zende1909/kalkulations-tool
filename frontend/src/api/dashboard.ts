import { api } from "./client";
import type { DashboardSummary } from "../types/dashboard";

export function getDashboardSummary(params?: { project?: string; customer?: string }) {
  const search = new URLSearchParams();
  if (params?.project) search.set("project", params.project);
  if (params?.customer) search.set("customer", params.customer);
  const query = search.toString();
  return api.get<DashboardSummary>(`/dashboard/summary${query ? `?${query}` : ""}`);
}
