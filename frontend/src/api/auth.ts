import { api } from "./client";
import type { LoginCredentials, TokenResponse, User } from "../types/auth";

export async function login(credentials: LoginCredentials): Promise<TokenResponse> {
  return api.post<TokenResponse>("/auth/login/json", credentials);
}

export async function getMe(): Promise<User> {
  return api.get<User>("/auth/me");
}
