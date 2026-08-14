const DEFAULT_API_URL = "http://127.0.0.1:8000/api/v1";

/**
 * In Vite-Dev bevorzugt relative URL (/api/v1) über den Proxy.
 * Absolut: 127.0.0.1 statt localhost (Windows IPv6 ::1-Problem).
 */
const API_URL = (import.meta.env.VITE_API_URL as string | undefined)?.trim() || DEFAULT_API_URL;

export function getApiBaseUrl(): string {
  return API_URL.replace(/\/$/, "");
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export class NetworkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NetworkError";
  }
}

export function getToken(): string | null {
  return localStorage.getItem("access_token");
}

export function setToken(token: string): void {
  localStorage.setItem("access_token", token);
}

export function clearToken(): void {
  localStorage.removeItem("access_token");
}

function formatDetail(detail: unknown): string {
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object") {
          const loc = Array.isArray((item as { loc?: unknown }).loc)
            ? (item as { loc: unknown[] }).loc.join(".")
            : "";
          const msg = (item as { msg?: string }).msg ?? JSON.stringify(item);
          return loc ? `${loc}: ${msg}` : msg;
        }
        return String(item);
      })
      .join("; ");
  }
  if (detail && typeof detail === "object") {
    return JSON.stringify(detail);
  }
  return "Anfrage fehlgeschlagen";
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    "Cache-Control": "no-cache, no-store, must-revalidate",
    Pragma: "no-cache",
    ...(options.headers || {}),
  };

  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const url = `${getApiBaseUrl()}${normalizedPath}`;
  const method = options.method ?? "GET";

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
      cache: "no-store",
    });
  } catch {
    throw new NetworkError(
      `Netzwerkfehler bei ${method} ${url}. ` +
        "Backend unter http://127.0.0.1:8000 erreichbar? " +
        "In der Dev-Umgebung sollte die API über /api/v1 (Vite-Proxy) laufen.",
    );
  }

  if (!response.ok) {
    let message = `HTTP ${response.status} bei ${method} ${url}`;
    try {
      const body = await response.json();
      message = formatDetail(body.detail) || message;
    } catch {
      // ignore parse errors
    }
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

/** Bust browser/proxy caches for list reloads after mutations. */
function withCacheBust(path: string): string {
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}_=${Date.now()}`;
}

export const api = {
  get: <T>(path: string) => request<T>(withCacheBust(path)),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  delete: (path: string) => request<void>(path, { method: "DELETE" }),
};
