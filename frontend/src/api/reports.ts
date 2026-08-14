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

export function dashboardPdfUrl(project?: string, customer?: string): string {
  const params = new URLSearchParams();
  if (project) params.set("project", project);
  if (customer) params.set("customer", customer);
  const q = params.toString();
  return `/reports/dashboard.pdf${q ? `?${q}` : ""}`;
}

export function dashboardXlsxUrl(project?: string, customer?: string): string {
  const params = new URLSearchParams();
  if (project) params.set("project", project);
  if (customer) params.set("customer", customer);
  const q = params.toString();
  return `/reports/dashboard.xlsx${q ? `?${q}` : ""}`;
}
