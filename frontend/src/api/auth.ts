import { api, ApiError, getApiBaseUrl, NetworkError } from "./client";
import type { LoginCredentials, TokenResponse, User } from "../types/auth";

/** OAuth2-Password-Flow: POST /auth/login als form-urlencoded (username/password). */
export async function login(credentials: LoginCredentials): Promise<TokenResponse> {
  const body = new URLSearchParams();
  body.set("username", credentials.email);
  body.set("password", credentials.password);

  const url = `${getApiBaseUrl()}/auth/login`;
  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
      cache: "no-store",
    });
  } catch {
    throw new NetworkError(
      `Netzwerkfehler bei POST ${url}. Backend unter http://127.0.0.1:8000 erreichbar?`,
    );
  }

  if (!response.ok) {
    let message = `HTTP ${response.status} bei POST ${url}`;
    try {
      const data = (await response.json()) as { detail?: unknown };
      if (typeof data.detail === "string") message = data.detail;
    } catch {
      // ignore
    }
    throw new ApiError(response.status, message);
  }

  return response.json() as Promise<TokenResponse>;
}

export async function getMe(): Promise<User> {
  return api.get<User>("/auth/me");
}
