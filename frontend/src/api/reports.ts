import { getApiBaseUrl, ApiError, getToken } from "./client";

export async function downloadReport(path: string, filename: string): Promise<void> {
  const token = getToken();
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const url = `${getApiBaseUrl()}${normalizedPath}`;

  const response = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    cache: "no-store",
  });

  if (!response.ok) {
    let message = `Export fehlgeschlagen (HTTP ${response.status})`;
    try {
      const body = await response.json();
      if (body.detail) {
        message = typeof body.detail === "string" ? body.detail : message;
      }
    } catch {
      // ignore
    }
    throw new ApiError(response.status, message);
  }

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

export function spritzgussPdfUrl(id: number): string {
  return `/reports/spritzguss/${id}.pdf`;
}

export function spritzgussXlsxUrl(id: number): string {
  return `/reports/spritzguss/${id}.xlsx`;
}

export function baugruppePdfUrl(id: number): string {
  return `/reports/baugruppen/${id}.pdf`;
}

export function baugruppeXlsxUrl(id: number): string {
  return `/reports/baugruppen/${id}.xlsx`;
}

export function dashboardPdfUrl(filters?: {
  project?: string;
  customer?: string;
  status?: string;
  date_from?: string;
  date_to?: string;
  kalkulationsart?: string;
}): string {
  const params = new URLSearchParams();
  if (filters?.project) params.set("project", filters.project);
  if (filters?.customer) params.set("customer", filters.customer);
  if (filters?.status) params.set("status", filters.status);
  if (filters?.date_from) params.set("date_from", filters.date_from);
  if (filters?.date_to) params.set("date_to", filters.date_to);
  if (filters?.kalkulationsart) params.set("kalkulationsart", filters.kalkulationsart);
  const q = params.toString();
  return `/reports/dashboard.pdf${q ? `?${q}` : ""}`;
}

export function dashboardXlsxUrl(filters?: {
  project?: string;
  customer?: string;
  status?: string;
  date_from?: string;
  date_to?: string;
  kalkulationsart?: string;
}): string {
  const params = new URLSearchParams();
  if (filters?.project) params.set("project", filters.project);
  if (filters?.customer) params.set("customer", filters.customer);
  if (filters?.status) params.set("status", filters.status);
  if (filters?.date_from) params.set("date_from", filters.date_from);
  if (filters?.date_to) params.set("date_to", filters.date_to);
  if (filters?.kalkulationsart) params.set("kalkulationsart", filters.kalkulationsart);
  const q = params.toString();
  return `/reports/dashboard.xlsx${q ? `?${q}` : ""}`;
}
